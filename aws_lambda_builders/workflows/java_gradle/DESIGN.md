# Java - Gradle Lambda Builder

## Scope

This package enables the creation of a Lambda deployment package for Java
projects managed using the Gradle build tool.

For Java projects, the most popular way to create a distribution package for
Java based Lambdas is to create an "uber" or "fat" JAR. This is a single JAR
file that contains both the customers' classes and resources, as well as all the
classes and resources extracted from their dependency JAR's. However, this can
cause files that have the same path in two different JAR's to collide within the
uber JAR.

Another solution is to create a distribution ZIP containing the customer's
classes and resources and include their dependency JARs under a `lib` directory.
This keeps the customers' classes and resources separate from their
dependencies' to avoid any file collisions. However, this incurs some overhead
as the ZIP must be unpacked before the code can run.

To avoid the problem of colliding files, we will choose the second option and
create distribution ZIP's by default. We can further provide the `--uber-jar`
option for customers to force the creation of an uber JAR if necessary. This
distribution will only contain the libraries needed at runtime (i.e. the runtime
classpath libraries).

Finally, a `--use-container` option will be provided to address potential issues
with environment-dependent build scripts (see Challenges).

## Challenges

Java bytecode can only run on the same or newer version of the JVM for which
it was compiled for. For example Java 8 bytecode can run a JVM that is at
least version 8, but bytecode targetting Java 9 cannot run on a Java 8 VM.
This is further complicated by the fact that a newer JDK can generate code to
be run on an older VM if configured using the `targetCompatibility` and
`sourceCompatibility` properties of the Java plugin. Therefore, it is not
sufficient to check the version of the local JDK, nor is it possible to check
the value set for `targetCompatibility` or `sourceCompatibility` since it can
be local to the compile/build task. At best, we can check if the local
version of the JDK is newer than Java 8 and emit a warning that the built
artifact may not run in Lambda.

Gradle projects are configured using `build.gradle` build scripts. These are
executable files authored in either Groovy or since 5.0, Kotlin, and using the
Gradle DSL. This presents a similar problem to `setup.py` in the Python world in
that arbitrary logic can be executed during build time that could affect both
how the customer's artifact is built, and which dependencies are chosen.

To solve the issue where the build environment could affect the `build.gradle`
script, a `--use-container` option will be provided, to give the option of
building in an environment that closely mimics the Lambda environment.

## Implementation

We leverage Gradle to do all the heavy lifting for executing the `build.gradle`
script which will resolve and download the dependencies and build the project.
To create the distribution ZIP, we insert a new Gradle `task` that packages the
compiled classes, resouces, and dependencies into a ZIP.

### sam build

#### Step 1: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `targetCompatibility`) or b) the project is
build within the Lambda-compatibile container.

#### Step 2: Synthesize a new build script

There is no standard task in Gradle to create a distribution ZIP (or uber JAR).
We must synthesize a new build script that we will run to actually produce the
Lambda artifact. This is so we can insert a new task that will assemble the
distribution ZIP. The new script is identical to the customer's original
`build.gradle` except that it imports our own `sam-ext.gradle` file provided by
this package.

It will do something similar to:

```sh
cp build.gradle build.gradle.sam-build

cp /path/to/sam-ext.gradle /tmp

echo 'apply from: "/tmp/sam-ext.gradle"' >> build.gradle.sam-build
```

where the contents of `sam-ext.gradle` contains the definition of the
`samBuildZip` task:

```gradle
// Include the project classes and resources in the root, and the dependencies
// under lib
task samBuildZip(type: Zip) {
    depends on build
    from sourceSets.main.output
    dependsOn configurations.runtimeClasspath
    into('lib') {
        from configurations.runtimeClasspath
    }
}
```

#### Step 3: Build and package

```sh
gradle -b build.gradle.sam-build samBuildZip
```

The `samBuildZip` task depends on the `build` task so we just run the
`samBuildZip` task.

### sam build --use-container

This will essentially be the same as `sam build` but run within the context of a
Lambda-like container, e.g. `lambci/lambda:java8`
