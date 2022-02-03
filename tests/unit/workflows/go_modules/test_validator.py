from unittest import TestCase

import mock
from parameterized import parameterized

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.workflows.go_modules.validator import GoRuntimeValidator
from aws_lambda_builders.exceptions import UnsupportedRuntimeError


class MockSubProcess(object):
    def __init__(self, returncode, out=b"", err=b""):
        self.returncode = returncode
        self.out = out
        self.err = err

    def communicate(self):
        return self.out, self.err


class TestGoRuntimeValidator(TestCase):
    def setUp(self):
        self.validator = GoRuntimeValidator(runtime="go1.x", architecture="arm64")

    def test_runtime_validate_unsupported_language_fail_open(self):
        validator = GoRuntimeValidator(runtime="go2.x", architecture="arm64")
        with self.assertRaises(UnsupportedRuntimeError):
            validator.validate(runtime_path="/usr/bin/go2")

    @parameterized.expand(
        [
            ("go1.11.2", (1, 11)),
            ("go1.11rc.2", (1, 11)),
            ("go1.16beta1", (1, 16)),
            ("go%$", (0, 0)),
            ("unknown", (0, 0)),
        ]
    )
    def test_get_go_versions(self, version_string, version_parts):
        self.assertEqual(self.validator.get_go_versions(version_string), version_parts)

    @parameterized.expand(
        [(b"go version go1.11.2 test",), (b"go version go1.11rc.2 test",), (b"go version go1.16beta1 test",)]
    )
    def test_runtime_validate_supported_version_runtime(self, go_version_output):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=go_version_output)
            self.validator.validate(runtime_path="/usr/bin/go")
            self.assertEqual(mock_subprocess.call_count, 1)

    def test_runtime_validate_supported_higher_than_min_version_runtime(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"go version go1.12 test")
            self.validator.validate(runtime_path="/usr/bin/go")
            self.assertEqual(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_nonzero_exit(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="/usr/bin/go")
                self.assertEqual(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_invalid_version(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"go version")
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="/usr/bin/go")
                self.assertEqual(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_minor_version(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"go version go1.10.2 test")
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="/usr/bin/go")
                self.assertEqual(mock_subprocess.call_count, 1)
