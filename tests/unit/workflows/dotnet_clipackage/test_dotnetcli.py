from unittest import TestCase
from mock import patch, MagicMock

from aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli import SubprocessDotnetCLI, DotnetCLIExecutionError


class TestSubprocessDotnetCLI(TestCase):
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value

    def test_dotnetcli_name_windows(self):
        self.os_utils.reset_mock()
        self.os_utils.is_windows.return_value = True

        dotnetCli = SubprocessDotnetCLI(os_utils=self.os_utils)

        assert dotnetCli.dotnet_exe == "dotnet.exe"

    def test_dotnetcli_name_non_windows(self):
        self.os_utils.reset_mock()
        self.os_utils.is_windows.return_value = False

        dotnetCli = SubprocessDotnetCLI(os_utils=self.os_utils)

        assert dotnetCli.dotnet_exe == "dotnet"

    def test_invalid_args(self):
        self.os_utils.reset_mock()
        self.os_utils.is_windows.return_value = True

        dotnetCli = SubprocessDotnetCLI(os_utils=self.os_utils)

        self.assertRaises(ValueError, dotnetCli.run, None)
        self.assertRaises(ValueError, dotnetCli.run, [])

    def test_success_exitcode(self):
        self.os_utils.reset_mock()
        self.os_utils.is_windows.return_value = True

        proc = MagicMock()
        mockStdOut = MagicMock()
        mockStdErr = MagicMock()
        proc.communicate.return_value = (mockStdOut, mockStdErr)
        proc.returncode = 0

        mockStdOut.decode.return_value = "useful info"
        mockStdErr.decode.return_value = "useful error"

        self.os_utils.popen.return_value = proc

        dotnetCli = SubprocessDotnetCLI(os_utils=self.os_utils)
        dotnetCli.run(["--info"])

    def test_error_exitcode(self):
        self.os_utils.reset_mock()
        self.os_utils.is_windows.return_value = True

        proc = MagicMock()
        mockStdOut = MagicMock()
        mockStdErr = MagicMock()
        proc.communicate.return_value = (mockStdOut, mockStdErr)
        proc.returncode = -1

        mockStdOut.decode.return_value = "useful info"
        mockStdErr.decode.return_value = "useful error"

        self.os_utils.popen.return_value = proc

        dotnetCli = SubprocessDotnetCLI(os_utils=self.os_utils)
        self.assertRaises(DotnetCLIExecutionError, dotnetCli.run, ["--info"])
