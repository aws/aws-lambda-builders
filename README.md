## Lambda Builders

[![AppVeyor Status](https://ci.appveyor.com/api/projects/status/txv6gk69614727nu?svg=true)](https://ci.appveyor.com/project/sanathkr/aws-lambda-builders-3bxwl)
[![Travis Status](https://travis-ci.org/awslabs/aws-lambda-builders.svg?branch=develop)](https://travis-ci.org/awslabs/aws-lambda-builders)

Lambda Builders is a Python library to compile, build and package AWS Lambda functions for several runtimes & 
frameworks.

Lambda Builders currently contains the following workflows

* Java with Gradle
* Java with Maven
* Dotnet with amazon.lambda.tools
* Python with Pip
* Javascript with Npm
* Ruby with Bundler
* Go with Dep
* Go with Mod

Lambda Builders is the brains behind the `sam build` command from [AWS SAM CLI](https://github.com/awslabs/aws-sam-cli)

If you are a developer and interested in contributing, read the [DESIGN DOCUMENT](./DESIGN.md) to understand how this works.
