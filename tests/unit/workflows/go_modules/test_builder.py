from unittest import TestCase

from mock import patch, Mock
from pathlib import Path

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflows.go_modules.builder import GoModulesBuilder, BuilderError


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestGoBuilder(TestCase):
    @patch("aws_lambda_builders.workflows.go_modules.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.handler = "cmd/helloWorld"
        self.popen = FakePopen()
        self.popen_go_case = FakePopen()
        self.osutils.popen.side_effect = [self.popen, self.popen_go_case]
        self.binaries = {"go": BinaryPath(resolver=Mock(), validator=Mock(), binary="go", binary_path="/path/to/go")}
        self.under_test = GoModulesBuilder(self.osutils, self.binaries, self.handler)

    def test_run_executes_bundler_on_nixes(self):
        self.osutils.is_windows.side_effect = [False]
        self.under_test = GoModulesBuilder(self.osutils, self.binaries, self.handler)
        self.under_test.build("source_dir", "output_path")
        self.osutils.popen.assert_called_with(
            ["/path/to/go", "build", "-o", "output_path", "source_dir"],
            cwd="source_dir",
            env={"GOOS": "linux", "GOARCH": "amd64"},
            stderr="PIPE",
            stdout="PIPE",
        )

    def test_build_gofiles_in_different_directory(self):
        self.popen.returncode = 1
        self.popen_go_case.returncode = 0
        self.osutils.is_windows.side_effect = [False]
        self.under_test = GoModulesBuilder(self.osutils, self.binaries, self.handler)
        self.under_test.build("source_dir_path", "output_path")

        self.osutils.popen.assert_called_with(
            ["/path/to/go", "build", "-o", "output_path", Path("source_dir_path/cmd/helloWorld")],
            cwd="source_dir_path",
            env={"GOOS": "linux", "GOARCH": "amd64"},
            stderr="PIPE",
            stdout="PIPE",
        )

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = b"some encoded text\n\n"
        result = self.under_test.build("source_dir", "output_path")
        self.assertEqual(result, "some encoded text")

    @patch("aws_lambda_builders.workflows.go_modules.builder.GoModulesBuilder._attempt_to_build_from_handler")
    def test_raises_BuilderError_with_err_text_if_retcode_is_not_0(self, patched_helper):
        patched_helper.return_value = self.popen, "", b"some error text\n\n"
        self.popen.returncode = 1
        self.popen.err = b"some error text\n\n"
        with self.assertRaises(BuilderError) as raised:
            self.under_test.build("source_dir", "output_path")
        self.assertEqual(raised.exception.args[0], "Builder Failed: some error text")

    def test_debug_configuration_set(self):
        self.under_test = GoModulesBuilder(self.osutils, self.binaries, self.handler, "Debug")
        self.under_test.build("source_dir", "output_path")
        self.osutils.popen.assert_called_with(
            ["/path/to/go", "build", "-gcflags", "all=-N -l", "-o", "output_path", "source_dir"],
            cwd="source_dir",
            env={"GOOS": "linux", "GOARCH": "amd64"},
            stderr="PIPE",
            stdout="PIPE",
        )

    def test_trimpath_configuration_set(self):
        self.under_test = GoModulesBuilder(self.osutils, self.binaries, self.handler, "release", "x86_64", True)
        self.under_test.build("source_dir", "output_path")
        self.osutils.popen.assert_called_with(
            ["/path/to/go", "build", "-trimpath", "-o", "output_path", "source_dir"],
            cwd="source_dir",
            env={"GOOS": "linux", "GOARCH": "amd64"},
            stderr="PIPE",
            stdout="PIPE",
        )

    def test_debug_configuration_set_with_arm_architecture(self):
        self.under_test = GoModulesBuilder(self.osutils, self.binaries, self.handler, "Debug", "arm64")
        self.under_test.build("source_dir", "output_path")
        self.osutils.popen.assert_called_with(
            ["/path/to/go", "build", "-gcflags", "all=-N -l", "-o", "output_path", "source_dir"],
            cwd="source_dir",
            env={"GOOS": "linux", "GOARCH": "arm64"},
            stderr="PIPE",
            stdout="PIPE",
        )
