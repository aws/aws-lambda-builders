## Path Resolver for Builders

### Scope

When building for a particular language, there are a few things to consider that a workflow currently already does. They are the following

* Language
* Dependency Manager
* Application framework

But what is missing is the ``path to the language executable``, that will be used for building artifacts through a workflow. 

Currently this is solved by just picking up the earliest instance of ``language`` in one's PATH. This works fine if there is just one instance of the language. This does not work in the case where there are more than one language version, with different executables living alongside one another in the path.

This path resolver given a language and a runtime, will attempt to resolve paths in an opioniated manner before falling back to the defaulting to the first executable in `$PATH`. The resolved path is then validated to check if the resolved path actually matches the runtime attributes specified. eg: version.

### Challenges

How do we come up with a mechanism that looks for different versions of the same executable in the PATH. One of the ways to look at this is to explicitly look for the runtime in the path ahead of the language.

eg:

```bash
Language | Runtime
python | python3.6, python3.7
```

In this case if our runtime is python3.6, we explicitly look for python3.6 in the path first. This also gives the flexibility to the user to easily change minor versions of the same executable, by just changing the a symlink.

We will need a resolver in each workflow, on being given a runtime and language combo return a path to the executable to be used for building artifacts.

### Interface

We will have a path resolver class, whose functionality is inherently simple to begin with. It has a candidate list of locations to look for the executable depending upon the runtime and language, and return the path.

```python
class PathResolver(object):
     def __init__(self, language, runtime):
        self.language = language
        self.runtime = runtime
        self.executables = [self.runtime, self.language]
        
     def path(self):
     	 path = ...
     	 return path
```

We will also have a runtime validator class to make sure that the path to the executable, is actually the executable we want to be building artifacts for.
This will do actions like making sure that version of the runtime specified, actually matches with the version from the executable path. Each Workflow can have its own validator that would do this.

```python

class RuntimeValidator(object):
	...
	...
	def validate_runtime(self, runtime_path):
		valid = ... (True/False based on some computation)
		return valid
```

The Base workflow will define a ```get_executable``` and a  ```get_validator``` method.

```python
class BaseWorkflow(object):
		...
		...
		...
	
	def get_executable(self):
		return PathResolver(language=x, runtime=x.y).path
	
	def get_validator(self):
		return RuntimeValidator(runtime_path=/usr/bin/x.y, language=x)
		
	@sanitize(executable_path=self.get_executable(),validator=self.get_validator())
	def run(self):
```

This way we have de-coupled validtion of the path and the actual finding of the path to the executable. Both of these methods can be over-riden in any workflow that subclasses BaseWorkflow.

There will be default implementations of ```PathResolver``` and ```RuntimeValidator``` that can still be used by workflow authors if they dont want to specialize them. 

A decorator on top of run, would actually execute validation on the resolved path to ensure that its safe to actually start the workflow.

### Implementation

Here is an Example of Python workflow that has ```get_executable``` and ```get_validator``` defined.

```python
class PythonPipWorkflow(object):
		...
		...
		...
	
	def get_executable(self):
		return PythonPathResolver(language=python, runtime=python3.6).path
	
	def get_validator(self):
		return PythonRuntimeValidator(runtime_path=/usr/bin/python3.6, language=python)
```

Finding the executable path and validation of the path occurs before the Workflow's ```run``` method is invoked. This way failure is detected early before workflow actions are executed.

There is a work in progress PR that partially follows this design doc, except it adds the the runtime_path in the per-language workflow. This will be changed to make it align with this design doc.

[#35](https://github.com/awslabs/aws-lambda-builders/pull/35)

### Tenets

The general tenets for this would look like as follows.

1. Every workflow needs to have a PathResolver and a Validator. The resolver can be a custom version or use the bundled opioniated resolver.
2. The workflow needs to fail if the resolved executable path does not match the supplied runtime version. This fails quickly and stops incorrect artifacts from being built.
3. The resolved executable path should be available to every action.

### Open questions

* Should we constrain the interface for the PathResolver with an abstract base class?
