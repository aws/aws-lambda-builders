# .NET Core - Lambda Builder

### Scope

To build .NET Core Lambda functions this builder will use the AWS .NET Core Global Tool [Amazon.Lambda.Tools](https://github.com/aws/aws-extensions-for-dotnet-cli#aws-lambda-amazonlambdatools).
This tool has several commands for building and publishing .NET Core Lambda functions. For this integration 
the `dotnet lambda package` command will be used to create a zip file that can be deployed to Lambda.

The builder will install the Amazon.Lambda.Tools Global Tool or update to the latest version before executing 
the package command.

This builder assumes the [.NET Core command-line interface (CLI)](https://docs.microsoft.com/en-us/dotnet/core/tools/?tabs=netcore2x) 
is already installed and added to the path environment variable. This is a reasonable requirement as the 
.NET Core CLI is a required tool for .NET Core developers to build any .NET Core project.

The .NET Core CLI handles the validation that the correct version of .NET Core is installed and errors out when there is 
not a correct version. 

### Challenges

#### Output

The output of `dotnet lambda package` command is a zip archive that consumers can then deploy to Lambda. For SAM build
the expected output is a directory of all of the output files. To make the package command compatible with the SAM build 
this builder will direct the package command to output the zip file in the artifacts folder. Once the package command is complete
it expands the zip file and then deletes the zip file.

#### Parameters

The package command takes in serveral parameters. Here is the help for the package command.
```bash
> dotnet lambda package --help
Amazon Lambda Tools for .NET Core applications (3.1.2)
Project Home: https://github.com/aws/aws-extensions-for-dotnet-cli, https://github.com/aws/aws-lambda-dotnet

package:
   Command to package a Lambda project into a zip file ready for deployment

   dotnet lambda package [arguments] [options]
   Arguments:
      <ZIP-FILE> The name of the zip file to package the project into
   Options:
      -c     | --configuration                Configuration to build with, for example Release or Debug.
      -f     | --framework                    Target framework to compile, for example net6.0.
      --msbuild-parameters                    Additional msbuild parameters passed to the 'dotnet publish' command. Add quotes around the value if the value contains spaces.
      -pl    | --project-location             The location of the project, if not set the current directory will be assumed.
      -cfg   | --config-file                  Configuration file storing default values for command line arguments.
      -pcfg  | --persist-config-file          If true the arguments used for a successful deployment are persisted to a config file.
      -o     | --output-package               The output zip file name
      -dvc   | --disable-version-check        Disable the .NET Core version check. Only for advanced usage.
```

Currently **--framework** is the only required parameter which tells the underlying build process what version of .NET Core to build for.

Parameters can be passed into the package command either by a config file called **aws-lambda-tools-defaults.json** or on 
the command line. All .NET Core project templates provided by AWS contain the **aws-lambda-tools-defaults.json** file which has
 configuration and framework set. 

If a parameter is set on the command line it will override any values set in the **aws-lambda-tools-defaults.json**. 
An alternative config file can be specified with the **--config-file** parameter.

This builder will forward any options that were provided to it starting with a '-' into the Lambda package command. Forwarding
all parameters to the Lambda package command keeps the builder future compatible with changes to the package command. The package
command does not error out for unknown parameters.

### Implementation

The implementation is broken up into 2 steps. The first action is to make sure the Amazon.Lambda.Tools Global Tool
is installed. The second action is to execute the `dotnet lambda package` command. 

#### Step 1: Install Amazon.Lambda.Tools

The tool is installed by executing the command `dotnet tool install -g Amazon.Lambda.Tools` This will install the
tool from [NuGet](https://www.nuget.org/packages/Amazon.Lambda.Tools/) the .NET package management system. 

To keep the tool updated the command `dotnet tool update -g Amazon.Lambda.Tools` will be executed if the install 
command fail because the tool was already installed.

It is a requirement for Amazon.Lambda.Tools to maintain backwards compatiblity for the package command. This is an
existing requirement for compatiblity with PowerShell Lambda support and the AWS Tools for Visual Studio Team Services.

#### Step 2: Build the Lambda Deployment bundle

To create the Lambda deployment bundle the `dotnet lambda package` command is execute in the project directory. This will 
create zip file in the artifacts directory. The builder will then expand the zip file into the zip artifacts folder and
delete the zip file.