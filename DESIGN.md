## Lambda Builders

- [Build Actions](#build-actions)
	- [Dependencies](#dependencies)
	- [Designs](#designs)
- [Builders Library](#builders-library)
	- [Command Line Interface (Internal)](#command-line-interface-internal)


Lambda Builders is a separate project that contains scripts to build Lambda functions, given a source location. It was
built as part of SAM CLI `sam build` command.Read https://github.com/awslabs/aws-sam-cli/pull/743 for design document 
explaining how Lambda Builders work in context of SAM CLI. 

This project has certain attributes that make it unique:

- Build Actions could be implemented in any programming language. Preferably in the language that they are building.
- Some build actions simply execute a binary (like Golang) without writing a Go script. 
  We provide generic Python runner to implement such build actions
- We have one build action for each Programming Language + Framework combination. 

### Build Actions
A build action is a module that knows how to build for a particular programming language & framework (ex: Python+PIP).
Build actions can be implemented in Python or in the native programming language.

If the builder is not written in Python, then it must have a CLI script that can be invoked directly from command 
line using the programming language binary (ex: `python python-pip/cli.py` or `node nodejs-npm/cli.js`). 
The CLI interface speaks the JSON-RPC protocol over stdin/stdout.

#### Dependencies 
If your build action implementation requires 3rd party libraries, here is how you deal with it:
 
- If the action is written in Python, then add the dependency to this project's manifest: `requirements/base.txt`
- If the action is not in Python, then vendor in all your dependencies with the action. For example, for JS libraries 
  include the `node_modules` folder along with your code. In future, we might create a `Makefile` target that can
  dynamically pull libraries before release and bundle it with the distribution. We do this to make sure the build 
  actions can work with minimal set of external libraries.
 
#### Designs

Each build action has its own design document. 

* [python-pip](./lambda_builders/actions/python_pip/DESIGN.md)


### Builders Library

This project is available as a Python Library & a wrapper CLI interface. Given a folder containing function's source
code, the selected build action, and path to an artifacts folder, this library will produce built artifacts in the
artifacts folder. 

Every build follows a standard workflow:

1. **Detect Manifest**: Verify the source contains a supported dependency manifest (ex: package.json or pom.xml)
1. **Resolve Dependencies**: Install dependencies
1. **Compile**: Optionally, compile the code if necessary
1. **Copy Source**: Optionally, Copy Lambda function code to the build folder

Build actions can choose to override one or more steps in this workflow. As much as possible, we encourage the actions
to make use of the default implementation. It helps reduce the variance in behavior between each action and provides
customers with a standard expectation. 

#### Command Line Interface (Internal)
This library provides a wrapper CLI interface for convenience. This interface is not supported at the moment. So we 
don't provide any guarantees of back compatibility. 

