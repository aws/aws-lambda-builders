"""
Actions for Ruby dependency resolution with Bundler
"""

import os
import logging

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .dotnetcli import DotnetCLIExecutionError

LOG = logging.getLogger(__name__)

class GlobalToolInstallAction(BaseAction):

    """
    A Lambda Builder Action which runs bundle install in order to build a full Gemfile.lock
    """

    NAME = 'GlobalToolInstall'
    DESCRIPTION = "Install or update the Amazon.Lambda.Tools .NET Core Global Tool."
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, subprocess_dotnet):
        super(GlobalToolInstallAction, self).__init__()
        self.subprocess_dotnet = subprocess_dotnet

    def execute(self):
        try:
            LOG.debug("Installing Amazon.Lambda.Tools Global Tool")
            self.subprocess_dotnet.run(
                ['tool', 'install', '-g', 'Amazon.Lambda.Tools'],
            )
        except DotnetCLIExecutionError as ex:
            LOG.debug("Error installing probably due to already installed. Attempt to update to latest version.")
            try:
                self.subprocess_dotnet.run(
                    ['tool', 'update', '-g', 'Amazon.Lambda.Tools'],
                )
            except DotnetCLIExecutionError as ex:
                raise ActionFailedError("Error configuring the Amazon.Lambda.Tools .NET Core Global Tool: " + str(ex))

class RunPackageAction(BaseAction):
    """
    A Lambda Builder Action which vendors dependencies to the vendor/bundle directory.
    """

    NAME = 'RunPackageAction'
    DESCRIPTION = "Execute the `dotnet lambda package` command."
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, subprocess_dotnet, artifacts_dir):
        super(RunPackageAction, self).__init__()
        self.source_dir = source_dir
        self.subprocess_dotnet = subprocess_dotnet
        self.artifacts_dir = artifacts_dir

    def execute(self):
        try:
            LOG.debug("Running bundle install --deployment in %s", self.source_dir)


            zipfile = os.path.basename(os.path.normpath(self.source_dir)) + ".zip"
            ziplocation = os.path.join(self.artifacts_dir, zipfile)
            self.subprocess_dotnet.run(
                ['lambda', 'package', '--output-package', ziplocation],
                cwd=self.source_dir
            )
        except DotnetCLIExecutionError as ex:
            raise ActionFailedError(str(ex))
