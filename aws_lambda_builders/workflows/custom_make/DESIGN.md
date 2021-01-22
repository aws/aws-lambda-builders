## Provided Make Builder

### Scope

Provided runtimes need a flexible builder approach as the binaries required for a building for each language is very different. The introduced builder should have scope
to be able build irrespective of the provided language, this is only possible if the logic of the build is not entirely contained within the builder itself, but that the builder 
executes commands that are user provided. The builder should showcase a contract to the user of how those commmands need to be provided.


### Mechanism

The Mechanism proposed here is that of `Makefile` Builder that has a particular make target available based on the logical id of the function to be built.
The `Makefile` is the manifest and is present in the same path as the original source directory.


### Implementation

When the makefile is called through a lambda builder workflow, the appropriate target is triggered and artifacts should be copied to the exposed environmental variable `$ARTIFACTS_DIR`. This environment variable is seeded by the lambda builder with a value set to it. The targets are defined as 

```
build-{Function_Logical_Id}
```

Injected Environment Variables by Makefile Lambda Builder Workflow per Function to be built. The injected environment variable has the path values modified
based on if this build mechanism is being run on windows (powershell or git bash).

``
ARTIFACTS_DIR=/Users/noname/sam-app/.aws-sam/build/HelloWorldFunction
``

Sample Makefile:

````
build-HelloWorldFunction:
    touch $(ARTIFACTS_DIR)/somefile

build-HelloWorldFunction2:
    touch $(ARTIFACTS_DIR)/somefile2
````

The workflow expects that the name of the function logical id is passed into the workflow using the `options` dictionary. This helps to trigger the correct build target.

#### Step 1: Copy source to a scratch directory

This involves the given source to a temporary scratch directory, so that mutations can be given on the files in the scratch directory, but leave the original source directory untouched.

#### Step 2: Core Workflow Action - Invoke Makefile Build Target

Artifacts directory is created if it doesnt exist and passed into the makefile target process.

```python
self.subprocess_make.run(["--makefile", self.manifest_path, f"build-{self.build_logical_id}"], env={"ARTIFACTS_DIR": self.artifacts_dir}, cwd=self.scratch_dir)
```

It is then the responsibility of the make target to make sure the artifacts are built in the correct manner and dropped into the artifacts directory.

### Challenges

* Is `make` truly platform independent?
  * Make comes with linux subsystem on windows and can also be installed with `choco`. 

* Does this become a way to introduce plugins, makefile can have any commands in it?
  * We only care about certain build targets. so essentially this is a pluggable builder, but nothing beyond that at this point in time.

* Which environment variables are usable in this makefile?
  * There are a series of allowlisted environment variables that need to be defined and not be overridden within the Makefile to work. Currently that is just `$ARTIFACTS_DIR`

* Can this be used even for runtimes that have builders associated with it? eg: python3.8?
  * Possibly, some changes would be needed be made to way the corresponding builder is picked up in sam cli. If we changed it such that there is a makefile we pick a makefile builder and if not fall back to the specified language builder.



