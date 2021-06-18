## Lambda Builders

- [Build Actions](#build-actions)
	- [Dependencies](#dependencies)
	- [Designs](#designs)
- [Builders Library](#builders-library)
	- [Command Line Interface (Internal)](#command-line-interface-internal)


Lambda Builders is a separate project that contains scripts to build Lambda functions, given a source location. It was
built as part of SAM CLI `sam build` command. Read https://github.com/awslabs/aws-sam-cli/pull/743 for design document
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

* [python-pip](./aws_lambda_builders/workflows/python_pip/DESIGN.md)


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
This library provides a wrapper CLI interface for convenience. This interface **is not supported** at the moment. So we
don't provide any guarantees of back compatibility.

It is a very thin wrapper over the library. It is meant to integrate
with tools written in other programming languages that can't import Python libraries directly. The CLI provides
[a JSON-RPC 2.0 interface](https://www.jsonrpc.org/specification)
over stdin/stdout to invoke the builder and get a response.

The CLI should be installed and available on the path:

```shell
pip install aws-lambda-builders
```

Each execution of `aws-lambda-builders` handles one JSON-RPC request.
Provide the whole body of the request via stdin, terminated by `EOF`.

Currently, the only exposed method is `LambdaBuilder.build`.
It closely maps to the
[Python method `LambdaBuilder.build` in `aws_lambda_builders/builder.py`](aws_lambda_builders/builder.py).

#### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "LambdaBuilder.build",
  "id": 1,
  "params": {
    "__protocol_version": "0.3",  // expected version of RPC protocol - from aws_lambda_builders/__main__.py
    "capability": {
      "language": "<programming language>",
      "dependency_manager": "<programming language framework>",
      "application_framework": "<application framework>"
    },
    "source_dir": "/path/to/source",
    "artifacts_dir": "/path/to/store/artifacts",
    "scratch_dir": "/path/to/tmp",
    "manifest_path": "/path/to/manifest.json",
    "runtime": "Function's runtime ex: nodejs8.10",
    "optimizations": {},  // not supported
    "options": {}  // depending on the workflow
  }
}
```

#### Successful Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {}  // Empty result indicates success
}
```

#### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": "",  // Integer code indicating the problem
    "message": "",  // Contains the Exception name 
    "data": ""   // Contains the exception message
  }  
}
```

#### Error Codes

Error codes returned by the application are similar to HTTP Status Codes.

- 400 - Similar to HTTP 400. Blame the caller.
- 500 - Internal server error
- 505 - RPC Protocol unsupported
- -32601 - Method unsupported (standard JSON-RPC protocol error code)

#### Params

##### `capability`
The 3-tuple `capability` is used to identify different workflows.
As of today, `application_framework` is unused and may be ignored.

##### `options`
The parameter `options` should be configured depending on the selected workflow/capability.

For more detail around the capabilities and options,
check out the corresponding _design document_ and `workflow.py` for
[the workflows you're interested in](aws_lambda_builders/workflows).

### Project Meta
#### Directory Structure
This project's directories are laid as follows:

```
aws_lambda_builders
├── __init__.py
├── __main__.py <- entrypoint for the CLI
├── action.py   <- This now just has the BaseAction class and any common language-agnostic Actions like CopySourceAction
├── runner.py    <- This is more or less the same as above.
├── workflows  <- Now instead of having all the builders/actions in one place, they are sorted by their language. You now need to use your technique to iterate these submodules and import the builders so that they get included in your registry.
│   ├── __init__.py
│   ├── dotnet_cli
│   │   ├── __init__.py
│   │   ├── actions.py
│   │   └── builders.py
│   ├── javascript_npm
│   │   ├── __init__.py
│   │   ├── npm_packager.js <- custom stuff would live alongside the python in these modules or in more subfolders.
│   │   ├── actions.py
│   │   └── builders.py
│   └── python_pip  <-- files in this directory do not have any convention. You can name them however you want
│       ├── __init__.py
│       ├── packager.py <- low level packager code that is called by the PythonPipResolveAction to do its job.
│       ├── actions.py  <- This now contains python specific actions like PythonPipResolveAction
│       └── builders.py <- The python specific builders would be defined here
├── exceptions.py
└── registry.py
```

Benefit here is that our high level build/action system is pulled out, and each language-specific piece acts almost like a plugin, its its own self contained directory. Someone could develop their own "package" with the structure

```
ruby
├── __init__.py
├── packager.rb
├── utils.rb
├── actions.py
└── builders.py
```

And essentially drop into the builders package (or maybe we can have a notion of a BUILDERS_PATH that is searched for these things and the default entry is this vended builders dir.) to get it to work. This seems the friendliest to me.

#### Terminologies

- **builder**: The entire project is called builder, because it can build Lambda functions
- **workflows**: Building for each language+framework combination is defined using a workflow. 
- **actions**: A workflow is implemented as a chain of actions.
