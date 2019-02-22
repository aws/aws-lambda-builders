Generic Builder Interface
=========================
This proposal suggests we evolve `aws-lambda-builders` to become a generic library for building all AWS code project types such as Lambda and ECS, providing a common library through which customer facing tools such as the CDK, SAM and ECS's CLI build and deploy customer's code.

What is the problem?
--------------------
Tools like the [Cloud Development Kit (CDK) CLI](https://github.com/awslabs/aws-cdk) and the [Elastic Contianer Service (ECS) CLI](https://github.com/aws/amazon-ecs-cli) require a single library to encapsulate the logic of assembling a project's source code into an artifact deployable to AWS. Since the CDK covers the entire surface area of AWS, not just serverless use-cases like SAM, the scope of `aws-lambda-builders` must be extended to include non-lambda target environments such as Docker images for ECR. This also asks questions of branding, perhaps requiring a new project named `aws-builders`.

The logic for mapping a project's structure to a workflow (e.g. looking for `pom.xml` or `build.gradle` to determine the java project type) is currently bundled into SAM CLI instead of `aws-lambda-builders`, burdening and limiting consumers.

Installing the `aws-lambda-builders` tool requires the use of `pip install`, which complicates the setup process of consumers such as the CDK (installed with `npm`) because instructions must be provided and followed by all customers to successfully set up their environment. Developers familiar with `npm` and looking to build a CDK project are now required to configure and manage tooling outside their initial intention. We must keep enviromental dependencies to a minimum.

What will be changed?
---------------------
Extract the automatic project inference from `sam cli` into this library and extend the RPC interface so that projects other than Lambda functions may also be built and packaged. 

Rename or create a new package, `aws-builders`, to better represent the (now) wider-surface area. 

Publish Docker images bundling the CLI for various target language/platforms so that consumers need not depend on `pip install` to consume the CLI. Instead, the tool can be invoked with [`docker run`](https://docs.docker.com/engine/reference/commandline/run/), requiring only a single dependency on the Docker toolchain. 

Taking a dependency on Docker is justified as follows:
* `aws-lambda-builders` already leverages Docker to build native code compatible with Lambda
* CDK already depends on Docker to build and push images to ECR, so no extra dependencies are required there.
* Docker successfully encapsulates the complexity of OS platforms and tool installations, allowing us to scale to a wide variety of use-cases without burdening our customers with toolchain dependencies.

Success criteria for the change
-------------------------------
A single library and CLI exists, encapsulating the logic to build deployable artifacts from arbitrary code workspaces. It should attempt to infer boiler-plate details such as maven vs gradle for building java, requiring only the language target from the caller. "This is a java 1.8 project, build it for me".

This CLI may be installed directly into the developer's environment or consumable as encapsulated Docker images specific to various langauges/environments.

User Experience Walkthrough
---------------------------

*TODO: More details/use-cases*

For the CDK use-case, we wish to instantiate a language-specific function type and only have to point to the project's location:

```ts
const myFunction = new lambda.JavaFunction(stack, 'MyJavaFunction', {
  projectPath: './lambda'
});
```

The CLI command `cdk synth` or `cdk deploy` will run a docker command to build the project into the `cdk.out` folder. In this example, we know to select the image for Java 1.8 because we know the function's runtime. 

The payload is a stripped down version of the existing RPC format,
```json
{
  "jsonrpc": "2.0",
  "method": "LambdaBuilder.build",
  "id": 1,
  "params": {
    "__protocol_version": "0.1",
    "capability": {
      "language": "java1.8", // signal from the caller, known because we know the function's runtime
      // don't specify the package manager, infer it in the builder tool
    },
    "source_dir": "/path/to/source",
    "artifacts_dir": "/path/to/cdk.out/",
    "scratch_dir": "/path/to/tmp",
  }
}
```

Implementation
==============

Design
------

*TODO: Explain how this feature will be implemented. Highlight the components
of your implementation, relationships* *between components, constraints,
etc.*

Open Issues
-----------
1. Do we want to rename this project or create a new package encapsulating the generic functionality?
2. What to do about `pip install`? Is there a better way to expose the CLI for local installation or inclusion in a `Dockerfile`?
3. Which environments/configurations should we publish Docker containers for? E.g. one container for NPM, one for Java, one for Python, etc. etc.
4. Do we want to provide hooks for developers to customize a build when their use-case is not supported?
5. What impact does supporting non-lambda targets have on the current architecture?

Task Breakdown
--------------

-   \[x\] Send a Pull Request with this design document
-   \[ \] Extract project inference from SAM CLI to `aws-lambda-builders`
-   \[ \] Update RPC to support the higher-level use cases (project inference)
-   \[ \] Publish a Docker image for each language we support (javascript, java, python, go mod, go dep)
-   \[ \] Document procedure for bundling this tool in a Docker container to support a new or custom target.
-   \[ \] Publish a Construct to the CDK demonstrating its use.