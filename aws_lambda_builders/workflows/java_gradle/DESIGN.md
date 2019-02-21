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

Here `ProjectA` is a a single lambda function, and `ProjectB` is a multi-build
project where sub directories `lambda1` and `lambda2` are each a lambda
function. In addition, suppose that `ProjectB/lambda1` has a dependency on its
sibling project `ProjectB/common`.

Building Project A is relatively simple since we just need to issue `gradlew
build` and place the built ZIP within the artifact directory.

Building `ProjectB/lambda1` is very similar from the point of view of the
workflow since it still issues the same command (`gradlew build`), but it
requires that Gradle is able to find its way back up to the parent `ProjectB` so
that it can also build `ProjectB/common` which can be a challenge when mounting
within a container.

## Implementation

### Build Workflow

We leverage Gradle to do all the heavy lifting for executing the
`build.gradle` script which will resolve and download the dependencies and
build the project. To create the distribution ZIP, we use the help of a
Gradle init script to insert a post-build action to do this.

#### Step 1: Copy custom init file to temporary location

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
gradle.project.afterProject { p ->
  // Set the give project's buildDir to one under SCRATCH_DIR
}

// Include the project classes and resources in the root, and the dependencies
// under lib
gradle.taskGraph.afterTask { t ->
    if (t.name != 'build') {
        return
    }

    // Step 1: Find the directory under scratch_dir where the artifact for
    // t.project is located
    // Step 2: Open ZIP file in $buildDir/distributions/lambda_build
    // Step 3: Copy project class files and resources to ZIP root
    // Step 3: Copy libs in configurations.runtimeClasspath into 'lib'
    // subdirectory in ZIP
}
```

#### Step 2: Resolve Gradle executable to use

[The recommended
way](https://docs.gradle.org/current/userguide/gradle_wrapper.html)  way to
author and distribute a Gradle project is to include a `gradlew` or Gradle
Wrapper file within the root of the project. This essentially locks in the
version of Gradle for the project and uses an executable that is independent of
any local installations. This helps ensure that builds are always consistent
over different environments.

The `gradlew` script, if it is included, will be located at the root of the
project. We will rely on the invoker of the workflow to supply the path to the
`gradlew` script.

We give precedence to this `gradlew` file, and if isn't found, we use the
`gradle` executable found on the `PATH` using the [path resolver][path resolver].

#### Step 3: Check Java version and emit warning

Check whether the local JDK version is <= Java 8, and if it is not, emit a
warning that the built artifact may not run in Lambda unless a) the project is
properly configured (i.e. using `targetCompatibility`) or b) the project is
built within a Lambda-compatibile environment like `lambci`.

We use the Gradle executable from Step 2 for this to ensure that we check the
actual JVM version Gradle is using in case it has been configured to use a
different one than can be found on the PATH.

#### Step 4: Build and package

```sh
$GRADLE_EXECUTABLE --project-cache-dir $SCRATCH_DIR/gradle-cache \
    -Dsoftware.amazon.aws.lambdabuilders.scratch-dir=$SCRATCH_DIR \
    --init-script $SCRATCH_DIR/lambda-build-init.gradle build
```

Since by default, Gradle stores its build-related metadata in a `.gradle`
directory under the source directory, we specify an alternative directory under
`scratch_dir` to avoid writing anything under `source_dir`. This is simply a
`gradle-cache` directory under `scratch_dir`.

Next, we also pass the location of the `scratch_dir` as a Java system
property so that it's availabe to our init script. This allows it to correctly
map the build directory for each sub-project within `scratch_dir`. Again, this
ensures that we are not writing anything under the source directory.

One important detail here is that the init script may create *multiple*
subdirectories under `scratch_dir`, one for each project involved in building
the lambda located at `source_dir`. Going back to the `ProjectB` example, if
we're building `lambda1`, this also has the effect of building `common` because
it's a declared dependency in its `build.gradle`. So, within `scratch_dir` will
be a sub directory for each project that gets built as a result of building
`source_dir`; in this case there will be one for each of `lambda1` and `common`.
The init file uses some way of mapping the source root of each project involved
to a unique directory under `scratch_dir`, like a hashing function.

#### Step 5: Copy to artifact directory

The workflow implementation is aware of the mapping scheme used to map a
`source_dir` to the correct directory under `scratch_dir` (described in step 4),
so it knows where to find the built Lambda artifact when copying it to
`artifacts_dir`. They will be located in
`$SCRATCH_DIR/<mapping for source_dir>/build/distributions/lambda-build`.

[path resolver]: https://github.com/awslabs/aws-lambda-builders/pull/55
