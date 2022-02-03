# Java - Maven Lambda Builder

## Scope

This package enables the creation of a Lambda deployment package for Java
projects managed using the Maven build tool.

## Challenges

- Java Version compatibility mentioned in the [Gradle Lambda Builder] Design doc.

- Building Multimodule project (out of scope for the current version)

Here `ProjectA` is a a single lambda function, and `ProjectB` is a multimodule
project where sub modules `lambda1` and `lambda2` are each a lambda
function. In addition, suppose that `ProjectB/lambda1` has a dependency on its
sibling module `ProjectB/common`.

**Single-module Project A**
```
ProjectA
├── pom.xml
├── src
└── template.yaml
```

**Multi-module Project B**
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
especially for the projects with multiple level of submodules. Building multi-module project is
out of scope for the current version.

## Implementation

### Build Workflow

#### Step 1: Copy source project to scratch directory

By default, Maven stores its build-related metadata in a `target`
directory under the source directory and there is no way to change the output 
directory from command line. To avoid writing anything under `source_dir`, 
we copy the source project to scratch directory and build it from there.

#### Step 2: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `maven.compiler.target`) or b) the project is
built within a Lambda-compatible environment like `lambci`.

We use Maven to check the actual JVM version Maven is using in case it has been 
configured to use a different one than can be found on the PATH.

#### Step 3: Build and package

We leverage Maven to do all the heavy lifting for executing the`mvn clean install` which
will resolve and download the dependencies and build the project. Built java classes 
will be located in `target/classes`. Then we use `mvn dependency:copy-dependenceis` to copy
the dependencies and the dependencies will be located in `target/dependency` under the 
source directory.

```bash
mvn clean install
mvn dependency:copy-dependencies -DincludeScope=runtime
```

Building artifact for an `AWS::Serverless::LayerVersion` requires different packaging than a 
`AWS::Serverless::Function`. [Layers](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
 use only artifacts under `java/lib/` which differs from Functions in that they in addition allow classes at 
the root level similar to normal jar packaging.  `JavaMavenLayersWorkflow` handles packaging for Layers and
`JavaMavenWorkflow` handles packaging for Functions.

#### Step 4: Copy to artifact directory

Built Java classes and dependencies for Functions are copied from `scratch_dir/target/classes` and `scratch_dir/target/dependency`
to `artifact_dir` and `artifact_dir/lib` respectively. Built Java classes and dependencies for Layers are copied from 
`scratch_dir/target/*.jar` and `scratch_dir/target/dependency` to  `artifact_dir/lib`. Copy all the artifacts 
required for runtime execution.

### Notes on changes of original implementation

The original implementation was not handling Layers well.  Maven has provided a scope called `provided` which is
used to declare that a particular dependency is required for compilation but should not be packaged with the
declaring project artifact.  Naturally this is the scope a maven java project would use for artifacts
provided by Layers.  Original implementation would package those `provided` scoped entities with the Function,
and thus if a project was using Layers it would have the artifact both in the Layer and in the Function.

[Gradle Lambda Builder]:https://github.com/awslabs/aws-lambda-builders/blob/develop/aws_lambda_builders/workflows/java_gradle/DESIGN.md