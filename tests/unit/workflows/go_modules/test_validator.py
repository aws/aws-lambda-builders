from unittest import TestCase

import mock
from parameterized import parameterized

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.workflows.go_modules.validator import GoRuntimeValidator


class MockSubProcess(object):

    def __init__(self, returncode, out=b"", err=b""):
        self.returncode = returncode
        self.out = out
        self.err = err

    def communicate(self):
        return (self.out, self.err)


class TestGoRuntimeValidator(TestCase):

    def setUp(self):
        self.validator = GoRuntimeValidator(runtime="go1.x")

    @parameterized.expand([
        "go1.x",
    ])
    def test_supported_runtimes(self, runtime):
        validator = GoRuntimeValidator(runtime=runtime)
        self.assertTrue(validator.has_runtime())

    def test_runtime_validate_unsupported_language_fail_open(self):
        validator = GoRuntimeValidator(runtime="go2.x")
        validator.validate(runtime_path="/usr/bin/go2")

    def test_runtime_validate_supported_version_runtime(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"go version go1.11.2 test")
            self.validator.validate(runtime_path="/usr/bin/go")
            self.assertTrue(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_nonzero_exit(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="/usr/bin/go")
                self.assertTrue(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_invalid_version(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"go version")
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="/usr/bin/go")
                self.assertTrue(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_minor_version(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"go version go1.10.2 test")
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="/usr/bin/go")
                self.assertTrue(mock_subprocess.call_count, 1)
