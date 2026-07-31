"""
Actions for .NET dependency resolution with CLI Package
"""

import logging
import os
import threading

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.workflow import BuildMode

from .dotnetcli import DotnetCLIExecutionError
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class GlobalToolInstallAction(BaseAction):
    __lock = threading.Lock()
    __tools_installed = False

    """
    A Lambda Builder Action which installs the Amazon.Lambda.Tools .NET Core Global Tool
    """

    NAME = "GlobalToolInstall"
    DESCRIPTION = "Install or update the Amazon.Lambda.Tools .NET Core Global Tool."
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, subprocess_dotnet, runtime=None):
        super(GlobalToolInstallAction, self).__init__()
        self.subprocess_dotnet = subprocess_dotnet
        self.runtime = runtime

    def _existing_tool_available(self):
        """
        Returns True if a working Amazon.Lambda.Tools is already available on the PATH
        (e.g. pre-installed in the SAM build image).
        """
        try:
            self.subprocess_dotnet.run(["lambda", "help"])
            return True
        except DotnetCLIExecutionError:
            return False

    def execute(self):
        # run Amazon.Lambda.Tools update in sync block in case build is triggered in parallel
        with GlobalToolInstallAction.__lock:
            LOG.debug("Entered synchronized block for updating Amazon.Lambda.Tools")

            # check if Amazon.Lambda.Tools updated recently
            if GlobalToolInstallAction.__tools_installed:
                LOG.info("Skipping to update Amazon.Lambda.Tools install/update, since it is updated recently")
                return

            # Amazon.Lambda.Tools 7.0.0 dropped support for dotnet6 (EOL runtime), so
            # installing/updating to latest breaks dotnet6 builds. If a working tool is
            # already available (e.g. pre-installed in the SAM build image), use it as is.
            # Deliberately not setting __tools_installed here so other runtimes in the
            # same process still install/update to latest as before.
            if self.runtime == "dotnet6" and self._existing_tool_available():
                LOG.info("Skipping Amazon.Lambda.Tools install/update for dotnet6; using the pre-installed version")
                return

            try:
                LOG.debug("Installing Amazon.Lambda.Tools Global Tool")
                self.subprocess_dotnet.run(["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"])
                GlobalToolInstallAction.__tools_installed = True
            except DotnetCLIExecutionError:
                LOG.debug("Error installing probably due to already installed. Attempt to update to latest version.")
                try:
                    self.subprocess_dotnet.run(
                        ["tool", "update", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
                    )
                    GlobalToolInstallAction.__tools_installed = True
                except DotnetCLIExecutionError as ex:
                    raise ActionFailedError(
                        "Error configuring the Amazon.Lambda.Tools .NET Core Global Tool: " + str(ex)
                    )


class RunPackageAction(BaseAction):
    """
    A Lambda Builder Action which builds the .NET Core project using the Amazon.Lambda.Tools .NET Core Global Tool

    :param source_dir: str
        Path to a folder containing the source code

    :param subprocess_dotnet:
        An instance of the dotnet process wrapper

    :param artifacts_dir: str
        Path to a folder where the built artifacts should be placed

    :param options:
        Dictionary of options ot pass to build action

    :param mode: str
        Mode the build should produce

    :param architecture: str
        Architecture to build for. Default value is X86_64 which is consistent with Amazon Lambda Tools

    :param os_utils:
        Optional, OS utils

    """

    NAME = "RunPackageAction"
    DESCRIPTION = "Execute the `dotnet lambda package` command."
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, subprocess_dotnet, artifacts_dir, options, mode, architecture=X86_64, os_utils=None):
        super(RunPackageAction, self).__init__()
        self.source_dir = source_dir
        self.subprocess_dotnet = subprocess_dotnet
        self.artifacts_dir = artifacts_dir
        self.options = options
        self.mode = mode
        self.architecture = architecture
        self.os_utils = os_utils if os_utils else OSUtils()

    def execute(self):
        try:
            LOG.debug("Running `dotnet lambda package` in %s", self.source_dir)

            zipfilename = os.path.basename(os.path.normpath(self.source_dir)) + ".zip"
            zipfullpath = os.path.join(self.artifacts_dir, zipfilename)

            arguments = [
                "lambda",
                "package",
                "--output-package",
                zipfullpath,
                # Pass function architecture to Amazon Lambda Tools.
                "--function-architecture",
                self.architecture,
                # Specify the architecture with the --runtime MSBuild parameter
                "--msbuild-parameters",
                "--runtime " + self._get_runtime(),
            ]

            if self.mode and self.mode.lower() == BuildMode.DEBUG:
                LOG.debug("Debug build requested: Setting configuration to Debug")
                arguments += ["--configuration", "Debug"]

            if self.options is not None:
                for key in self.options:
                    if str.startswith(key, "-"):
                        arguments.append(key)
                        arguments.append(self.options[key])

            self.subprocess_dotnet.run(arguments, cwd=self.source_dir)

            # The dotnet lambda package command outputs a zip file for the package. To make this compatible
            # with the workflow, unzip the zip file into the artifacts directory and then delete the zip archive.
            self.os_utils.unzip(zipfullpath, self.artifacts_dir)

        except DotnetCLIExecutionError as ex:
            raise ActionFailedError(str(ex))

    def _get_runtime(self):
        """
        Returns the msbuild runtime for the action architecture

        Returns
        -------
        str
            linux-arm64 if ARM64, linux-x64 otherwise
        """
        return "linux-arm64" if self.architecture == ARM64 else "linux-x64"
