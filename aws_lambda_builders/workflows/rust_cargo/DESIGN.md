# Rust Cargo Builder

## Scope

This package enables the creation of a Lambda deployment package for Rust projects managed using the [cargo](https://doc.rust-lang.org/cargo/) build tool targeting Lambda's "provided" runtime. Rust support for the provided runtime is bundled as a compilation dependency of these projects, provided by the [lambda](https://github.com/awslabs/aws-lambda-rust-runtime) crate.

## Implementation

This package uses [Cargo Lambda](https://www.cargo-lambda.info) to do all the heavy lifting for cross compilation, target validation, and other executable optimizations.

It supports X86-64 architectures with the target `x86_64-unknown-linux-gnu` by default. It also supports ARM architectures with the target option `aarch64-unknown-linux-gnu`. Those are the only two valid targets. The target is automatically configured based on the `architecture` option in the `RustCargoLambdaWorkflow`.

The general algorithm for preparing a rust executable for use on AWS Lambda is as follows.

### Build

It builds a binary in the standard cargo target directory. The binary's name is always `bootstrap`, and it's always located under `target/lambda/HANDLER_NAME/bootstrap`.

For a Cargo workspace, the build targets the workspace's shared `target` directory rather than a `target` directory under each member. Because `sam build` invokes this workflow once per function, sharing a single target directory lets cargo compile common dependencies once instead of recompiling the whole dependency tree for every function. The shared directory and the member's binary name are both read from a single `cargo metadata` call. For a standalone (non-workspace) project the shared `target` directory is the project's own — unchanged from prior behavior. An explicit `CARGO_TARGET_DIR` in the environment always takes precedence.

### Copy and Rename executable

It then copies the executable to the target directory honoring the provided runtime's [expectation on executable names](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html).

Because every workspace member now builds into the same `target/lambda` directory, that directory holds all of the workspace's binaries. When no handler (`artifact_executable_name`) is given, the copy step selects the binary named for the package whose manifest lives in the function's source directory (from the same `cargo metadata` call). It falls back to the previous single-directory heuristic when the binary name cannot be resolved.

If two or more workspace members define a `bin` target with the same name (for example each package declaring a `bootstrap` bin), those binaries compile to the same path in the shared directory and overwrite each other. `sam build` still produces correct artifacts because it copies each function's binary out immediately after building it, but this relies on build ordering, so the workflow logs a warning recommending unique bin names per function.

## Notes

Like the go builders, the workflow argument `options.artifact_executable_name`
interface can used to provide a handler name that resolves to an executable. This
enables sam support for cargo workspaces allowing for one rust project to have multiple lambdas. Cargo workspaces have a notion of a `package` and `bin`. A `package` can have
multiple bins but typically `packages` have a 1-to-1 relationship with a default `bin`: `main.rs`. The handler names must be uniques across a Rust project, regardless of how many packages and binaries that project includes.
