## NodeJS - NPM Lambda Builder

### Scope

The scope for this builder is to take an existing
directory containing customer code, including a valid `package.json` manifest
specifying third-party dependencies. The builder will use NPM to include
production dependencies and exclude test resources in a way that makes them
deployable to AWS Lambda.

### Challenges

NPM normally stores all dependencies in a `node_modules` subdirectory. It
supports several dependency categories, such as development dependencies
(usually third-party build utilities and test resources), optional dependencies
(usually required for local execution but already available on the production
environment, or peer-dependencies for optional third-party packages) and
production dependencies (normally the minimum required for correct execution).
All these dependency types are mixed in the same directory.

To speed up Lambda startup time and optimise usage costs, the correct thing to
do in most cases is just to package up production dependencies. During development 
work we can expect that the local `node_modules` directory contains all the 
various dependency types, and NPM does not provide a way to directly identify
just the ones relevant for production. 

There are two ways to include only production dependencies in a package:

1. **without a bundler**: Copy the source to a clean temporary directory and
   re-run dependency installation there. 

2. **with a bundler**: Apply a javascript code  bundler (such as `esbuild` or
   `webpack`) to produce a single-file javascript bundle by recursively
   resolving included dependencies, starting from the main lambda handler.
  
A frequently used trick to speed up NodeJS Lambda deployment is to avoid 
bundling the `aws-sdk`, since it is already available on the Lambda VM.
This makes deployment significantly faster for single-file lambdas, for
example. Although this is not good from a consistency and compatibility
perspective (as the version of the API used in production might be different
from what was used during testing), people do this frequently enough that the
packager should handle it in some way. A common way of marking this with ClaudiaJS
is to include `aws-sdk` as an optional dependency, then deploy without optional
dependencies. 

Other runtimes do not have this flexibility, so instead of adding a specific
parameter to the SAM CLI, the packager should support a flag to include or
exclude optional dependencies through environment variables. 

NPM also provides support for running user-defined scripts as part of the build
process, so this packager needs to support standard NPM script execution.

NPM, since version 5, uses symbolic links to optimise disk space usage, so
cross-project dependencies will just be linked to elsewhere on the local disk 
instead of included in the `node_modules` directory. This means that just copying
the `node_modules` directory (even if symlinks would be resolved to actual paths)
far from optimal to create a stand-alone module. Copying would lead to significantly
larger packages than necessary, as sub-modules might still have test resources, and
common references from multiple projects would be duplicated.

NPM also uses two locking mechanisms (`package-lock.json` and `npm-shrinkwrap.json`) 
that can be used to freeze versions of dependencies recursively, and provide reproducible
builds. Before version 7, the locking mechanism was in many ways more
broken than functional, as it in some cases hard-codes locks to local disk
paths, and gets confused by including the same package as a dependency
throughout the project tree in different dependency categories
(development/optional/production). Although the official tool recommends
including this file in the version control, as a way to pin down dependency
versions, when using on several machines with different project layout it can
lead to uninstallable dependencies. 

NPM dependencies are usually plain javascript libraries, but they may include
native binaries precompiled for a particular platform, or require some system 
libraries to be installed. A notable example is `sharp`, a popular image 
manipulation library, that uses symbolic links to system libraries. Another 
notable example is `puppeteer`, a library to control a headless Chrome browser,
that downloads a Chromium binary for the target platform during installation.

To fully deal with those cases, this packager may need to execute the
dependency installation step on a Docker image compatible with the target
Lambda environment.

### Choosing the packaging type

For a large majority of projects, packaging using a bundler has significant
advantages (speed and runtime package size, supporting local dependencies). 

However, there are also some drawbacks to using a bundler for a small set of
use cases (namely including packages with binary dependencies, such as `sharp`, a
popular image processing library). 

Because of this, it's important to support both ways of packaging. The version
without a bundler is slower, but will be correct in case of binary dependencies.
For backwards compatibility, this should be the default.

Users should be able to activate packaging with a bundler for projects where that
is safe to do, such as those without any binary dependencies. 

The proposed approach is to use a "aws-sam" property in the package manifest 
(`package.json`). If the `nodejs_npm` Lambda builder finds a matching property, it 
knows that it is safe to use the bundler to package.

The rest of this section outlines the major differences between packaging with
and without a bundler.

#### packaging speed

Packaging without a bundler is slower than using a bundler, as it
requires copying the project to a clean working directory, installing
dependencies and archiving into a single ZIP.  

Packaging with a bundler runs directly on files already on the disk, without
the need to copy or move files around. This approach can use the fast `npm ci`
command to just ensure that the dependencies are present on the disk instead of
always downloading all the dependencies.

#### additional tools

Packaging without a bundler does not require additional tools installed on the
development environment or CI systems, as it can just work with NPM.  

Packaging with a bundler requires installing additional tools (eg `esbuild`).

#### handling local dependencies

Packaging without a bundler requires complex
rewriting to handle local dependencies, and recursively packaging archives. In
theory, this was going to be implemented as a subsequent release after the
initial version of the `npm_nodejs` builder, but due to issues with container
environments and how `aws-lambda-builders` mounts the working directory, it was
not added for several years, and likely will not be implemented soon.

Packaging with a bundler can handle local dependencies out of the box, since
it just traverses relative file liks. 

#### including non-javascript files

Packaging without a bundler zips up entire contents of NPM packages.

Packaging with a bundler only locates JavaScript files in the dependency tree.

Some NPM packages include important binaries or resources in the NPM package,
which would not be included in the package without a bundler. This means that
packaging using a bundler is not universally applicable, and may never fully
replace packaging without a bundler.

Some NPM packages include a lot of additional files not required at runtime.
`aws-sdk` for JavaScript (v2) is a good example, including TypeScript type
definitions, documentation and REST service definitions for automated code
generators.  Packaging without a bundler includes these files as well,
unnecessarily increasing Lambda archive size. Packaging with a bundler just
ignores all these additional files out of the box.

#### error reporting

Packaging without a bundler leaves original file names and line numbers, ensuring
that any stack traces or exception reports correspond directly to the original 
source files.

Packaging with a bundler creates a single file from all the dependencies, so
stack traces on production no longer correspond to original source files. As a
workaround, bundlers can include a 'source map' file, to allow translating
production stack traces into source stack traces. Prior to Node 14, this
required including a separate NPM package, or additional tools. Since Node 14,
stack trace translation can be [activated using an environment
variable](https://serverless.pub/aws-lambda-node-sourcemaps/)


### Implementation without a bundler

The general algorithm for preparing a node package for use on AWS Lambda
without a JavaScript bundler (`esbuild` or `webpack`) is as follows.

#### Step 1: Prepare a clean copy of the project source files

Execute `npm pack` to perform project-specific packaging using the supplied
`package.json` manifest, which will automatically exclude temporary files, 
test resources and other source files unnecessary for running in a production 
environment.

This will produce a `tar` archive that needs to be unpacked into the artifacts
directory.  Note that the archive will actually contain a `package`
subdirectory containing the files, so it's not enough to just directly unpack
files. 

#### Step 2: Rewrite local dependencies

_(out of scope for the current version)_

To optimise disk space and avoid including development dependencies from other
locally linked packages, inspect the `package.json` manifest looking for dependencies
referring to local file paths (can be identified as they start with `.` or `file:`),
then for each dependency recursively execute the packaging process 

Local dependencies may include other local dependencies themselves, this is a very 
common way of sharing configuration or development utilities such as linting or testing 
tools. This means that for each packaged local dependency this packager needs to
recursively apply the packaging process. It also means that the packager needs to 
track local paths and avoid re-packaging directories it already visited.

NPM produces a `tar` archive while packaging that can be directly included as a
dependency.  This will make NPM unpack and install a copy correctly. Once the
packager produces all `tar` archives required by local dependencies, rewrite
the manifest to point to `tar` files instead of the original location.

If the project contains a package lock file, this will cause NPM to ignore changes
to the package.json manifest. In this case, the packager will need to remove 
`package-lock.json` so that dependency rewrites take effect. 
_(out of scope for the current version)_

#### Step 3: Install dependencies

The packager should then run `npm install` to download an expand all dependencies to
the local `node_modules` subdirectory. This has to be executed in the directory with
a clean copy of the source files.

Note that NPM can be configured to use proxies or local company repositories using 
a local file, `.npmrc`. The packaging process from step 1 normally excludes this file, so it needs 
to be copied before dependency installation, and then removed. 

Some users may want to exclude optional dependencies, or even include development dependencies. 
To avoid incompatible flags in the `sam` CLI, the packager should allow users to specify 
options for the `npm install` command using an environment variable.
_(out of scope for the current version)_

To fully support dependencies that download or compile binaries for a target platform, this step
needs to be executed inside a Docker image compatible with AWS Lambda. 
_(out of scope for the current version)_

### Implementation with a bundler

The general algorithm for preparing a node package for use on AWS Lambda
with a bundler (`esbuild` or `webpack`) is as follows.

#### Step 1: ensure production dependencies are installed

If the directory contains `package-lock.json` or `npm-shrinkwrap.json`, 
execute [`npm ci`](https://docs.npmjs.com/cli/v7/commands/npm-ci). This 
operation is designed to be faster than installing dependencies using `npm install`
in automated CI environments.

If the directory does not contain lockfiles, but contains `package.json`,
execute [`npm install --production`] to download production dependencies.

#### Step 2: bundle the main Lambda file

Execute `esbuild` to produce a single JavaScript file by recursively resolving
included dependencies, and optionally a source map.

Ensure that the target file name is the same as the entry point of the Lambda
function, so that there is no impact on the CloudFormation template.


### Activating the bundler workflow

Because there are advantages and disadvantages to both approaches (with and
without a bundler), the user should be able to choose between them. The default
is not to use a bundler (both because it's universally applicable and for
backwards compatibility). Node.js pakage manifests (`package.json`) allow for
custom properties, so a user can activate the bundler process by providing an
`aws_sam` configuration property in the package manifest. If this property is
present in the package manifest, and the sub-property `bundler` equals
`esbuild`, the Node.js NPM Lambda builder activates the bundler process.

Because the Lambda builder workflow is not aware of the main lambda function
definition, (the file containing the Lambda handler function) the user must
also specify the main entry point for bundling . This is a bit of an
unfortunate duplication with SAM Cloudformation template, but with the current
workflow design there is no way around it.

In addition, as a single JavaScript source package can contain multiple functions,
and can be included multiple times in a single CloudFormation template, it's possible
that there may be multiple entry points for bundling. SAM build executes the build
only once for the function in this case, so all entry points have to be bundled
at once.

The following example is a minimal `package.json` to activate the `esbuild` bundler
on a javascript file, starting from `lambda.js`. It will produce a bundled `lambda.js`
in the artifacts folder.

```json
{
  "name": "nodeps-esbuild",
  "version": "1.0.0",
  "license": "APACHE2.0",
  "aws_sam": {
    "bundler": "esbuild",
    "entry_points": ["lambda.js"]
  }
}
```

#### Locating the esbuild binary

`esbuild` supports platform-independent binary distribution using NPM, by
including the `esbuild` package as a dependency. The Lambda builder should 
first try to locate the binary in the Lambda code repository (allowing the 
user to include a specific version). Failing that, the Lambda builder should
try to locate the `esbuild` binary in the `executable_search_paths` configured
for the workflow, then the operating system `PATH` environment variable. 

The Lambda builder **should not** bring its own `esbuild` binary, but it should
clearly point to the error when one is not found, to allow users to configure the 
build correctly.

In the previous example, the esbuild binary is not included in the package dependencies,
so the Lambda builder will use the system executable paths to search for it. In the 
example below, `esbuild` is included in the package, so the Lambda builder should use it
directly.

```json
{
  "name": "with-deps-esbuild",
  "version": "1.0.0",
  "license": "APACHE2.0",
  "aws_sam": {
    "bundler": "esbuild",
    "entry_points": ["lambda.js"]
  },
  "devDependencies": {
    "esbuild": "^0.11.23"
  }
}
```

For a full example, see the [`with-deps-esbuild`](../../../tests/integration/workflows/nodejs_npm_esbuild/testdata/with-deps-esbuild/) test project.

#### Building typescript

`esbuild` supports bundling typescript out of the box and transpiling it to plain
javascript. The user just needs to point to a typescript file as the main entry point,
as in the example below. There is no transpiling process needed upfront.


```js
{
  "name": "with-deps-esbuild-typescript",
  "version": "1.0.0",
  "license": "APACHE2.0",
  "aws_sam": {
    "bundler": "esbuild",
    "entry_points": ["included.ts"]
  },
  "dependencies": {
    "@types/aws-lambda": "^8.10.76"
  },
  "devDependencies": {
    "esbuild": "^0.11.23"
  }
}
```

For a full example, see the [`with-deps-esbuild-typescript`](../../../tests/integration/workflows/nodejs_npm_esbuild/testdata/with-deps-esbuild-typescript/) test project.

**important note:** esbuild does not perform type checking, so users wanting to ensure type-checks need to run the `tsc` process as part of their 
testing flow before invoking `sam build`. For additional typescript caveats with esbuild, check out <https://esbuild.github.io/content-types/#typescript>.

#### Configuring the bundler

The Lambda builder invokes `esbuild` with sensible defaults that will work for the majority of cases. Importantly, the following three parameters are set by default

* `--minify`, as it [produces a smaller runtime package](https://esbuild.github.io/api/#minify)
* `--sourcemap`, as it generates a [source map that allows for correct stack trace reporting](https://esbuild.github.io/api/#sourcemap) in case of errors (see the [Error reporting](#error-reporting) section above)
* `--target es2020`, as it allows for javascript features present in Node 14

Users might want to tweak some of these runtime arguments for a specific project, for example not including the source map to further reduce the package size, or restricting javascript features to an older version. The Lambda builder allows this with optional sub-properties of the `aws_sam` configuration property.

* `target`: string, corresponding to a supported [esbuild target](https://esbuild.github.io/api/#target) property
* `minify`: boolean, defaulting to `true`
* `sourcemap`: boolean, defaulting to `true`

Here is an example that deactivates minification and source maps, and supports JavaScript features compatible with Node.js version 10.

```json
{
 "aws_sam": {
    "bundler": "esbuild",
    "entry_points": ["included.ts"],
    "target": "node10",
    "minify": false,
    "sourcemap": false
  }
}
