# Java - Maven Lambda Builder

## Scope

This package enables the creation of a Lambda deployment package for Java
projects managed using the Maven build tool.

## Challenges

- Java Version compatibility mentioned in the java_grade Design doc.

- Building Multimodule project

Here `ProjectA` is a a single lambda function, and `ProjectB` is a multimodule
project where sub modules `lambda1` and `lambda2` are each a lambda
function. In addition, suppose that `ProjectB/lambda1` has a dependency on its
sibling module `ProjectB/common`.

**Single Project A**
```
ProjectA
├── pom.xml
├── src
└── template.yaml
```

**Multmodule Project B**
```
ProjectB
├── common
│   └── pom.xml
├── lambda1
│   └── pom.xml
├── lambda2
│   └── pom.xml
├── pom.xml
└── template.yaml
```

Building Project A is relatively simple since we just need to issue `mvn
package` and place the built classes and dependency jars within the artifact directory.

Building `ProjectB/lambda1` requires maven to build `lambda1` module from
the root pom directory and use `--also-make` option to build necessary dependencies 
(`ProjectB/common`  in this case) first before building `ProjectB/lambda1`. This is because
maven is not able to find its way back up to the parent `ProjectB` to
also build `ProjectB/common`. The challenge part here is to find the parent pom directory 
especially for the projects with multiple level of submodules. The following implementation 
assumes aws-lambda-builders have knowledge of the root package path for multimodule project.

## Implementation

### Build Workflow

We leverage Maven to do all the heavy lifting for executing the
`mvn package` which will resolve and download the dependencies and
build the project.

#### Step 1: Copy source project to scratch directory

By default, Maven stores its build-related metadata in a `target`
directory under the source directory and there is no way to change the output 
directory from command line. To avoid writing anything under `source_dir`, 
we copy the source project to scratch directory and build it from there.

#### Step 2: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `targetCompatibility`) or b) the project is
built within a Lambda-compatibile environment like `lambci`.

We use Maven to check the actual JVM version Maven is using in case it has been 
configured to use a different one than can be found on the PATH.

#### Step 3: Build and package

```sh
# Single Project
mvn package
mvn dependency:copy-dependencies

# Multimodule Project
cd /path/to/rootdirectory
mvn install -pl :MODULE_TO_BUILD -also-make
mvn dependency:copy-dependencies -pl :MODULE_TO_BUILD
```

Generate java classes will be located in `target/classes` and dependencies 
will be located in `target/dependency` under the source directory in `scratch_dir`.

#### Step 4: Copy to artifact directory

The workflow implementation is aware of the mapping scheme used to map a
`source_dir` to the correct directory under `scratch_dir` (described in step 4),
so it knows where to find the built Lambda artifact when copying it to
`artifacts_dir`. They will be located in
`$SCRATCH_DIR/<mapping for source_dir>/target`.
