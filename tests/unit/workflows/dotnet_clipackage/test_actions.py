from unittest import TestCase

import os
import platform
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from parameterized import parameterized

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli import DotnetCLIExecutionError
from aws_lambda_builders.workflows.dotnet_clipackage.actions import GlobalToolInstallAction, RunPackageAction


@patch.object(GlobalToolInstallAction, "_GlobalToolInstallAction__installed_version", None)
class TestGlobalToolInstallAction(TestCase):
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli.SubprocessDotnetCLI")
    def setUp(self, MockSubprocessDotnetCLI):
        self.subprocess_dotnet = MockSubprocessDotnetCLI.return_value

    def tearDown(self):
        self.subprocess_dotnet.reset_mock()
        GlobalToolInstallAction._GlobalToolInstallAction__installed_version = None

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

    def test_global_tool_parallel(self):
        actions = [
            GlobalToolInstallAction(self.subprocess_dotnet),
            GlobalToolInstallAction(self.subprocess_dotnet),
            GlobalToolInstallAction(self.subprocess_dotnet),
        ]

        with ThreadPoolExecutor() as executor:
            for action in actions:
                executor.submit(action.execute)

        self.subprocess_dotnet.run.assert_called_once_with(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
        )

    def test_global_tool_install_dotnet6_pins_version(self):
        action = GlobalToolInstallAction(self.subprocess_dotnet, runtime="dotnet6")
        action.execute()
        self.subprocess_dotnet.run.assert_called_once_with(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources", "--version", "5.13.2"]
        )

    def test_global_tool_update_dotnet6_pins_version(self):
        self.subprocess_dotnet.run.side_effect = [DotnetCLIExecutionError(message="Already Installed"), None]
        action = GlobalToolInstallAction(self.subprocess_dotnet, runtime="dotnet6")
        action.execute()
        self.subprocess_dotnet.run.assert_any_call(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources", "--version", "5.13.2"]
        )
        self.subprocess_dotnet.run.assert_any_call(
            ["tool", "update", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources", "--version", "5.13.2"]
        )

    def test_global_tool_install_other_runtimes_no_version_pin(self):
        action = GlobalToolInstallAction(self.subprocess_dotnet, runtime="dotnet8")
        action.execute()
        self.subprocess_dotnet.run.assert_called_once_with(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
        )

    def test_dotnet6_pins_version_even_after_dotnet8_installs_latest(self):
        # dotnet8 builds first — installs latest (no pin)
        dotnet8_action = GlobalToolInstallAction(self.subprocess_dotnet, runtime="dotnet8")
        dotnet8_action.execute()
        self.subprocess_dotnet.run.assert_called_once_with(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources"]
        )
        self.subprocess_dotnet.reset_mock()

        # dotnet6 builds next — must re-pin to 5.14.0, not skip
        dotnet6_action = GlobalToolInstallAction(self.subprocess_dotnet, runtime="dotnet6")
        dotnet6_action.execute()
        self.subprocess_dotnet.run.assert_called_once_with(
            ["tool", "install", "-g", "Amazon.Lambda.Tools", "--ignore-failed-sources", "--version", "5.13.2"]
        )


class TestRunPackageAction(TestCase):
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli.SubprocessDotnetCLI")
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.utils.OSUtils")
    def setUp(self, MockSubprocessDotnetCLI, MockOSUtils):
        self.subprocess_dotnet = MockSubprocessDotnetCLI.return_value
        self.os_utils = MockOSUtils.return_value
        self.source_dir = "/source_dir"
        self.artifacts_dir = "/artifacts_dir"
        self.scratch_dir = "/scratch_dir"

    def tearDown(self):
        self.subprocess_dotnet.reset_mock()
        self.os_utils.reset_mock()

    def test_build_package(self):
        mode = "Release"

        options = {}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, os_utils=self.os_utils
        )

        action.execute()

        zip_path = os.path.join(self.artifacts_dir, "source_dir.zip")

        self.subprocess_dotnet.run.assert_called_once_with(
            [
                "lambda",
                "package",
                "--output-package",
                zip_path,
                "--function-architecture",
                X86_64,
                "--msbuild-parameters",
                "--runtime linux-x64",
            ],
            cwd="/source_dir",
        )

    def test_build_package_x86(self):
        mode = "Release"

        options = {}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, X86_64, os_utils=self.os_utils
        )

        action.execute()

        zip_path = os.path.join(self.artifacts_dir, "source_dir.zip")

        self.subprocess_dotnet.run.assert_called_once_with(
            [
                "lambda",
                "package",
                "--output-package",
                zip_path,
                "--function-architecture",
                X86_64,
                "--msbuild-parameters",
                "--runtime linux-x64",
            ],
            cwd="/source_dir",
        )

    def test_build_package_arm64(self):
        mode = "Release"

        options = {}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, ARM64, os_utils=self.os_utils
        )

        action.execute()

        zip_path = os.path.join(self.artifacts_dir, "source_dir.zip")

        self.subprocess_dotnet.run.assert_called_once_with(
            [
                "lambda",
                "package",
                "--output-package",
                zip_path,
                "--function-architecture",
                ARM64,
                "--msbuild-parameters",
                "--runtime linux-arm64",
            ],
            cwd="/source_dir",
        )

    @parameterized.expand(
        [
            ("net6.0"),
            ("net8.0"),
        ]
    )
    def test_build_package_arguments(self, dotnet_version):
        mode = "Release"
        options = {"--framework": dotnet_version}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, os_utils=self.os_utils
        )

        action.execute()

        zip_path = self.artifacts_dir + ("\\" if platform.system().lower() == "windows" else "/") + "source_dir.zip"

        self.subprocess_dotnet.run.assert_called_once_with(
            [
                "lambda",
                "package",
                "--output-package",
                zip_path,
                "--function-architecture",
                X86_64,
                "--msbuild-parameters",
                "--runtime linux-x64",
                "--framework",
                dotnet_version,
            ],
            cwd="/source_dir",
        )

    def test_build_error(self):
        mode = "Release"

        self.subprocess_dotnet.run.side_effect = DotnetCLIExecutionError(message="Failed Package")
        options = {}
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, os_utils=self.os_utils
        )

        self.assertRaises(ActionFailedError, action.execute)

    def test_debug_configuration_set(self):
        mode = "Debug"
        options = None
        action = RunPackageAction(
            self.source_dir, self.subprocess_dotnet, self.artifacts_dir, options, mode, os_utils=self.os_utils
        )

        zip_path = os.path.join("/", "artifacts_dir", "source_dir.zip")

        action.execute()

        self.subprocess_dotnet.run.assert_called_once_with(
            [
                "lambda",
                "package",
                "--output-package",
                zip_path,
                "--function-architecture",
                X86_64,
                "--msbuild-parameters",
                "--runtime linux-x64",
                "--configuration",
                "Debug",
            ],
            cwd="/source_dir",
        )
