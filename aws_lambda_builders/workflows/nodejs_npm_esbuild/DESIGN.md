## NodeJS - NPM Lambda Builder Using `esbuild`

### Scope

The scope for this builder is to take an existing
directory containing customer code, including a valid `package.json` manifest
specifying third-party dependencies. The builder will use NPM to include
production dependencies and exclude test resources in a way that makes them
deployable to AWS Lambda. It will then bundle the code using `esbuild` with the properties
passed in through the builder options field.

### Additional Tools

Packaging with a bundler requires installing additional tools (eg `esbuild`).

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
function.

### Activating the bundler workflow

The workflow can be activated by using the `("nodejs", "npm-esbuild", None)` Capability.
The distinguishing factor being the `npm-esbuild` dependency-manager property of the builder.

An entrypoint or entrypoints array must be included in the options passed
to Lambda Builders for this workflow to succeed.

The following example is a minimal options object that can be passed to
the esbuild workflow, starting from `lambda.js`. It will produce a bundled `lambda.js`
in the artifacts folder.

```json
{
  "options": {
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

If no file type is provided for the entrypoint, esbuild will first look for a
TypeScript file, and the a JavaScript file with the given filename.

```js
{
  "name": "with-deps-esbuild-typescript",
  "version": "1.0.0",
  "license": "APACHE2.0",
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
    "entry_points": ["included.ts"],
    "target": "node10",
    "minify": false,
    "sourcemap": false
}
