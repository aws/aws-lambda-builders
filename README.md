## Lambda Builders

![Apache 2.0 License](https://img.shields.io/github/license/aws/aws-lambda-builders)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/aws/aws-lambda-builders)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aws-lambda-builders)
![pip](https://img.shields.io/badge/pip-aws--lambda--builders-9cf)

Lambda Builders is a Python library to compile, build and package AWS Lambda functions for several runtimes & 
frameworks.

Lambda Builders currently contains the following workflows

* Java with Gradle
* Java with Maven
* Dotnet with amazon.lambda.tools
* Python with Pip
* Javascript with Npm
* Typescript with esbuild
* Ruby with Bundler
* Go with Mod
* Rust with Cargo

In Addition to above workflows, AWS Lambda Builders also supports *Custom Workflows* through a Makefile.

Lambda Builders is the brains behind the `sam build` command from [AWS SAM CLI](https://github.com/awslabs/aws-sam-cli)

### Integrating with Lambda Builders

Lambda Builders is a Python library.
It additionally exposes a JSON-RPC 2.0 interface to use from other languages.

If you intend to integrate with Lambda Builders,
check out [this section of the DESIGN DOCUMENT](DESIGN.md#builders-library).

### Contributing

If you are a developer and interested in contributing, read the [DESIGN DOCUMENT](./DESIGN.md) to understand how this works.
