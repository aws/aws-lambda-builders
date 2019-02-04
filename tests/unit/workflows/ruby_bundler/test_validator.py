from unittest import TestCase

import mock
from parameterized import parameterized

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.workflows.ruby_bundler.validator import RubyRuntimeValidator

class MockSubProcess(object):

    def __init__(self, returncode, out=b"", err=b""):
        self.returncode = returncode
        self.out = out
        self.err = err

    def communicate(self):
        return (self.out, self.err)

class TestRubyRuntimeValidator(TestCase):
    def setUp(self):
        self.validator = RubyRuntimeValidator(runtime="ruby2.5")

    @parameterized.expand(["ruby2.5"])
    def test_supported_runtimes(self, runtime):
        validator = RubyRuntimeValidator(runtime=runtime)
        self.assertTrue(validator.has_runtime())

    def test_unsupported_runtime(self):
        validator = RubyRuntimeValidator(runtime="ruby2.4")
        self.assertFalse(validator.has_runtime())

    def test_unsupported_runtime_validation(self):
        validator = RubyRuntimeValidator(runtime="ruby2.4")
        self.assertFalse(validator.validate(runtime_path="bundler"))

    def test_runtime_validate_zero_exit(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"")
            self.validator.validate(runtime_path="bundler")
            self.assertTrue(mock_subprocess.call_count, 1)
            self.assertEqual("bundler", self.validator.validated_runtime_path)

    def test_runtime_validate_mismatch_nonzero_exit(self):
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path="bundler")
                self.assertTrue(mock_subprocess.call_count, 1)
