from unittest import TestCase
from mock import patch
import os
import platform

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli import DotnetCLIExecutionError
from aws_lambda_builders.workflows.dotnet_clipackage.actions import GlobalToolInstallAction, RunPackageAction


class TestGlobalToolInstallAction(TestCase):
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli.SubprocessDotnetCLI")
    def setUp(self, MockSubprocessDotnetCLI):
        self.subprocess_dotnet = MockSubprocessDotnetCLI.return_value

    def tearDown(self):
        self.subprocess_dotnet.reset_mock()

    def test_global_tool_install(self):
        action = GlobalToolInstallAction(self.subprocess_dotnet)
        action.execute()
        self.subprocess_dotnet.run.assert_called_once_with(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
        )

    def test_global_tool_update(self):
        self.subprocess_dotnet.run.side_effect = [DotnetCLIExecutionError(message="Already Installed"), None]
        action = GlobalToolInstallAction(self.subprocess_dotnet)
        action.execute()
        self.subprocess_dotnet.run.assert_any_call(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
        )
        self.subprocess_dotnet.run.assert_any_call(
            ["tool", "update", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
        )

    def test_global_tool_update_failed(self):
        self.subprocess_dotnet.run.side_effect = [
            DotnetCLIExecutionError(message="Already Installed"),
            DotnetCLIExecutionError(message="Updated Failed"),
        ]
        action = GlobalToolInstallAction(self.subprocess_dotnet)
        self.assertRaises(ActionFailedError, action.execute)


class TestRunPackageAction(TestCase):
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli.SubprocessDotnetCLI")
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.utils.OSUtils")
    def setUp(self, MockSubprocessDotnetCLI, MockOSUtils):
        self.subprocess_dotnet = MockSubprocessDotnetCLI.return_value
        self.os_utils = MockOSUtils
        self.source_dir = os.path.join("/source_dir")
        self.artifacts_dir = os.path.join("/artifacts_dir")
        self.scratch_dir = os.path.join("/scratch_dir")

    def tearDown(self):
        self.subprocess_dotnet.reset_mock()

    def test_build_package(self):
        mode = "Release"

        options = {}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, self.os_utils
        )

        action.execute()

        zipFilePath = os.path.join("/", "artifacts_dir", "source_dir.zip")

        self.subprocess_dotnet.run.assert_called_once_with(
            ["lambda", "package", "--output-package", zipFilePath], cwd="/source_dir"
        )

    def test_build_package_arguments(self):
        mode = "Release"
        options = {"--framework": "netcoreapp2.1"}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, self.os_utils
        )

        action.execute()

        if platform.system().lower() == "windows":
            zipFilePath = "/artifacts_dir\\source_dir.zip"
        else:
            zipFilePath = "/artifacts_dir/source_dir.zip"

        self.subprocess_dotnet.run.assert_called_once_with(
            ["lambda", "package", "--output-package", zipFilePath, "--framework", "netcoreapp2.1"], cwd="/source_dir"
        )

    def test_build_error(self):
        mode = "Release"

        self.subprocess_dotnet.run.side_effect = DotnetCLIExecutionError(message="Failed Package")
        options = {}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, self.os_utils
        )

        self.assertRaises(ActionFailedError, action.execute)

    def test_debug_configuration_set(self):
        mode = "Debug"
        options = None
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, self.os_utils
        )

        zipFilePath = os.path.join("/", "artifacts_dir", "source_dir.zip")

        action.execute()

        self.subprocess_dotnet.run.assert_called_once_with(
            ["lambda", "package", "--output-package", zipFilePath, "--configuration", "Debug"], cwd="/source_dir"
        )
