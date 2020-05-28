# Rust Cargo Builder

## Scope

This package enables the creation of a Lambda deployment package for Rust projects managed using the [cargo](https://doc.rust-lang.org/cargo/) build tool targeting Lambda's "provided" runtime. Rust support for the provided runtime is bundled as a compilation dependency of these projects, provided by the [lambda](https://github.com/awslabs/aws-lambda-rust-runtime) crate.

## Implementation

The general algorithm for preparing a rust executable for use on AWS Lambda
is as follows.

### Build

It builds a binary in the standard cargo target directory. 

### Copy and Rename executable

It then copies the executable to the target directory renaming the executable to "bootstrap" to honor the provided runtime's [expectation on executable names](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html).

## Challenges

### Cross compilation

Cargo builds binaries targeting host platforms. When the host platform is not the same as the target platform it leverages a parameterized notion of a named target, typically installed and managed by [rustup](https://github.com/rust-lang/rustup). In the case of `sam` we default this target to to `x86_64-unknown-linux-musl` when the host is not linux based.

Users can simply run `rustup target add x86_64-unknown-linux-musl` if needed. It's also possible for sam to detect this when needed and do that for users by parsing the output of `rustup target list --installed` but it would be unusual for sam to
install toolchain components on a users behalf.

The challenge is not installing the cargo target. The challenge is ensuring external linker dependencies of that target are present at build time. Setting this up varies from platform to platform. And example for osx can be found [here](https://www.andrew-thorburn.com/cross-compiling-a-simple-rust-web-app/). This may warrant requiring a building inside a docker container that is linux based.

## Notes

Like the go builders, the workflow argument `options.artifact_executable_name`
interface is used to provide a handler name that resolves to an executable. This
enables sam support for cargo workspaces allowing for one rust project to have multiple lambdas. Cargo workspaces have a notion of a `package` and `bin`. A `package` can have
multiple bins but typically `packages` have a 1-to-1 relationship with a default `bin`: `main.rs`. 

The following table defines handler name to package/bin semantics.

| Handler name | Package | Bin |
|--------------|---------|-----|
| foo          | foo     | foo |
| foo.foo      | foo     | foo |
| foo.bar      | foo     | bar |