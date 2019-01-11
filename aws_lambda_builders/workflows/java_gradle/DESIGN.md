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
create distribution ZIP.

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

An interesting challenge is dealing with single build and multi build projects.
Consider the following different projects structures:

**Project A**
```
ProjectA
├── build.gradle
├── gradlew
├── src
└── template.yaml
```

**Project B**
```
ProjectB
├── common
│   └── build.gradle
├── lambda1
│   └── build.gradle
├── lambda2
│   └── build.gradle
├── build.gradle
├── gradlew
├── settings.gradle
└── template.yaml
```

Building Project A is relatively simple since we just need to issue `gradlew
build` and place the built ZIP within the artifact directory.

Building Project B is a little more complicated. Starting at the top of the
directory, we begin by issuing `gradlew build` as before. However, since we have
now built multiple functions, we need *multiple* artifact directories, one for
each function. The build workflow must have some way of mapping each function's
artifact to the correct artifact directory.

## Implementation

### Source directory, and artifact directory semantics

To enable the multi build projects where a Gradle project can contain multiple
Lambdas as individual child projects, the builder behavior will change depending
on whether the `options` provided to the build command contains a map called
`artifact_mapping`.

When this map is **not** present, the semantics of `source_dir` and
`artifact_dir` are not changed.

If this map is present, then `source_dir` is treated as the root directory of
the parent project. Additionally, `artifact_dir` will not be the path under
which the artifact will be copied to, but just the parent of the final
directory. `artifact_mapping` will be a mapping from a source subdirectory under
`source_dir` (i.e. the location of the inidividual function code), to a sub
directory under the given `artifact_dir` where the function's artifacts will be
copied to.

### Build Workflow

We leverage Gradle to do all the heavy lifting for executing the
`build.gradle` script which will resolve and download the dependencies and
build the project. To create the distribution ZIP, we use the help of a
Gradle init script to insert a post-build action to do this.


#### Step 1: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `targetCompatibility`) or b) the project is
built within a Lambda-compatibile environment like `lambci`.

The [path resolver][path resolver] will be used for help in validating.

#### Step 2: Copy custom init file to temporary location

There is no standard task in Gradle to create a distribution ZIP (or uber JAR).
We add this functionality through the use of a Gradle init script. The script
will be responsible for adding a post-build action that creates the distribution
ZIP.

It will do something similar to:

```sh
cp /path/to/lambda-build-init.gradle /$SCRATCH_DIR/
```

where the contents of `lambda-build-init.gradle` contains the code for defining
the post-build action:

```gradle
// Include the project classes and resources in the root, and the dependencies
// under lib
gradle.taskGraph.afterTask { t ->
    if (t.name != 'build') {
        return
    }

    // Step 1: Open ZIP file in $buildDir/distributions
    // Step 2: Copy project class files and resources to ZIP root
    // Step 3: Copy libs in configurations.runtimeClasspath into 'lib'
    // subdirectory in ZIP
}
```

#### Step 3: Resolve Gradle executable to use

A popular way to author and distribute a Gradle project is to include a
`gradlew` or Gradle Wrapper file within the root of the project. This
essentially locks in the version of Gradle for the project and uses an
executable that is independent of any local installations.

The `gradlew` script, if it is included, will be located at the root of the
project. We make the assumption that `source_dir` is always at the project root,
so we simply check if `gradlew` exists under `source_dir`.

We give precedence to this `gradlew` file, and if isn't found, we use the
`gradle` executable found using the [path resolver][path resolver].

#### Step 3: Build and package

```sh
$GRADLE_EXECUTABLE --init-script /$SCRATCH_DIR/lambda-build-init.gradle build
```

[path resolver]: https://github.com/awslabs/aws-lambda-builders/pull/55
