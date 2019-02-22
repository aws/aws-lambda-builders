# Java - Maven Lambda Builder

## Scope

This package enables the creation of a Lambda deployment package for Java
projects managed using the Maven build tool.

## Challenges

- Java Version compatibility mentioned in the [Gradle Lambda Builder] Design doc.

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

#### Step 1: Copy source project to scratch directory

By default, Maven stores its build-related metadata in a `target`
directory under the source directory and there is no way to change the output 
directory from command line. To avoid writing anything under `source_dir`, 
we copy the source project to scratch directory and build it from there.

*TODO*: For multi-module project, we need to know the root directory
in order to copy the whole project.

#### Step 2: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `targetCompatibility`) or b) the project is
built within a Lambda-compatibile environment like `lambci`.

We use Maven to check the actual JVM version Maven is using in case it has been 
configured to use a different one than can be found on the PATH.

#### Step 3: Build and package

We leverage Maven to do all the heavy lifting for executing the`mvn package` which
will resolve and download the dependencies and build the project. Built java classes 
will be located in `target/classes`. Then we use `mvn dependency:copy-dependenceis` to copy
the dependencies and the dependencies will be located in `target/dependency` under the 
source directory.

##### Single-module project

```bash
mvn clean package 
mvn dependency:copy-dependencies -DincludeScope=compile
```

##### Multi-module project

```bash
cd /path/to/rootdirectory
mvn clean install -pl :$SOURCE_DIRECTORY_NAME --also-make
mvn dependency:copy-dependencies -pl :$SOURCE_DIRECTORY_NAME -DincludeScope=compile
```

Here `$SOURCE_DIRECTORY_NAME` is the name of the source directory of the project. Maven
will build the dependencies of that project in the reactor and then build the project itself.
Note that `mvn install` is being used for multimodule project and this is because 
`dependency:copy-dependencies`  requires all dependencies being installed in the local repository.

```bash
# Example commands to build ProjectB/lambda1
cd ..
mvn clean install -pl :lambda1 --also-make # build common first then lambda1
mvn dependency:copy-dependencies -pl :lambda1 -DincludeScope=compile
```

#### Step 4: Copy to artifact directory

Built Java classes and dependencies are copied from `scratch_dir/target/classes` and `scratch_dir/target/dependency`
to `artifact_dir` and `artifact_dir/lib` respectively.

[Gradle Lambda Builder]:https://github.com/awslabs/aws-lambda-builders/blob/develop/aws_lambda_builders/workflows/java_gradle/DESIGN.md