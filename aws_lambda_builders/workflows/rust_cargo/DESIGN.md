# Rust Cargo Builder

## Scope

This package enables the creation of a Lambda deployment package for Rust projects managed using the [cargo](https://doc.rust-lang.org/cargo/) build tool targeting Lambda's "provided" runtime. Rust support for the provided runtime is bundled as a compilation dependency of these projects, provided by the [lambda](https://github.com/awslabs/aws-lambda-rust-runtime) crate.

## Implementation

This package uses [Cargo Lambda](https://www.cargo-lambda.info) to do all the heavy lifting for cross compilation, target validation, and other executable optimizations.

It supports X86-64 architectures with the target `x86_64-unknown-linux-gnu` by default. It also supports ARM architectures with the target option `aarch64-unknown-linux-gnu`. Those are the only two valid targets. The target is automatically configured based on the `architecture` option in the `RustCargoLambdaWorkflow`.

The general algorithm for preparing a rust executable for use on AWS Lambda is as follows.

### Build

It builds a binary in the standard cargo target directory. The binary's name is always `bootstrap`, and it's always located under `target/lambda/HANDLER_NAME/bootstrap`.

### Copy and Rename executable

It then copies the executable to the target directory honoring the provided runtime's [expectation on executable names](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html).

## Notes

Like the go builders, the workflow argument `options.artifact_executable_name`
interface can used to provide a handler name that resolves to an executable. This
enables sam support for cargo workspaces allowing for one rust project to have multiple lambdas. Cargo workspaces have a notion of a `package` and `bin`. A `package` can have
multiple bins but typically `packages` have a 1-to-1 relationship with a default `bin`: `main.rs`. The handler names must be uniques across a Rust project, regardless of how many packages and binaries that project includes.
