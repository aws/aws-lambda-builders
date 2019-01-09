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
        self.validator = GoRuntimeValidator(runtime="go1.x", runtime_path="/usr/bin/go")

    @parameterized.expand([
        ("go1.x", "/usr/bin/go"),
    ])
    def test_supported_runtimes(self, runtime, runtime_path):
        validator = GoRuntimeValidator(runtime=runtime, runtime_path=runtime_path)
        self.assertTrue(validator.has_runtime())

    def test_runtime_validate_unsupported_language_fail_open(self):
        validator = GoRuntimeValidator(runtime='go2.x', runtime_path='/usr/bin/go2')
        validator.validate_runtime()

    def test_runtime_validate_supported_version_runtime(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out='go version go1.11.2 test')
            self.validator.validate_runtime()
            self.assertTrue(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_version_runtime(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate_runtime()
                self.assertTrue(mock_subprocess.call_count, 1)
