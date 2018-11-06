## Lambda Builders

Lambda Builders is a separate project that contains scripts to build Lambda functions, given a source location. It was
built as part of SAM CLI `sam build` command.Read https://github.com/awslabs/aws-sam-cli/pull/743 for design document 
explaining how Lambda Builders work in context of SAM CLI. 

Eventually, we will move this library into a separate code repository so other tools can consume it. 

This project has certain attributes that make it unique:

- Builders could be implemented in any programming language. Preferably in the language that they are building.
- Some builders simply execute a binary (like Golang) without writing a Go script. We provide generic Python runner to implement 
  such builders
- We have one builder for each Programming Language + Framework combination. 


### Scope of Builders

- Each builder must have a CLI script that can be invoked directly from command line using the programming language
  binary (ex: `python python-pip/cli.py` or `node nodejs-npm/cli.js`). The CLI interface speaks the JSON-RPC protocol.
  
- Each builder also has a public module that can be directly imported in the language 
  (ex: `from python-pip.rpc import builder`). This method takes same argument as the ones passed through JSON-RPC.
  In fact, the CLI interface literally parses JSON-RPC and calls method. 
  
 
