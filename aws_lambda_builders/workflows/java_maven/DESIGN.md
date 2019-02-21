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

#### Step 1: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `targetCompatibility`) or b) the project is
built within a Lambda-compatibile environment like `lambci`.

We use Maven to check the actual JVM version Maven is using in case it has been 
configured to use a different one than can be found on the PATH.

#### Step 2: Build and package

We leverage Maven to do all the heavy lifting for executing the`mvn package` which
will resolve and download the dependencies and build the project. Built java classes 
will be located in `target/classes`. Then we use `mvn dependency:copy-dependenceis` to copy
the dependencies and the dependencies will be located in `target/dependency` under the 
source directory.

##### Single project

```sh
mvn package 
mvn dependency:copy-dependencies
```

##### Multimodule project

```bash
cd /path/to/rootdirectory
mvn install -pl :$SOURCE_DIRECTORY_NAME --also-make
mvn dependency:copy-dependencies -pl :$SOURCE_DIRECTORY_NAME
```

Here `$SOURCE_DIRECTORY_NAME` is the name of the source directory of the project. Maven
will build the dependencies of that project in the reactor and then build the project itself.
Note that `mvn install` is being used for multimodule project and this is because 
`dependency:copy-dependencies`  requires all dependencies being installed in the local repository.

```bash
# Example commands to build ProjectB/lambda1
cd ..
mvn install -pl :lambda1 --also-make # build common first then lambda1
mvn dependency:copy-dependencies -pl :lambda1
```

#### Step 3: Copy to artifact directory

Built Java classes and depedenceis are copied from `source_dir/target/classes` and `source_dir/target/dependency`
respectively to the artifact directory.

#### Step 4: Clean up target directory

By default, Maven stores its build-related metadata in a `target`
directory under the source directory and we run `mvn clean` to clean up
the directory.

##### Single project

```sh
mvn clean 
```

##### Multimodule project

```sh
cd /path/to/rootdirectory
mvn clean
```

[Gradle Lambda Builder]:https://github.com/awslabs/aws-lambda-builders/blob/develop/aws_lambda_builders/workflows/java_gradle/DESIGN.md