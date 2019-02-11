from unittest import TestCase

import mock
from mock import patch

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
    @patch("aws_lambda_builders.workflows.ruby_bundler.bundler.SubprocessBundler")
    def setUp(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        self.validator = RubyRuntimeValidator(
            runtime="ruby2.5",
            bundler=subprocess_bundler
        )

    @patch("aws_lambda_builders.workflows.ruby_bundler.bundler.SubprocessBundler")
    def test_supported_runtimes(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        validator = RubyRuntimeValidator(
            runtime="ruby2.5",
            bundler=subprocess_bundler
        )
        self.assertTrue(validator.has_runtime())

    @patch("aws_lambda_builders.workflows.ruby_bundler.bundler.SubprocessBundler")
    def test_unsupported_runtime(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        validator = RubyRuntimeValidator(
            runtime="ruby2.4",
            bundler=subprocess_bundler
        )
        self.assertFalse(validator.has_runtime())

    @patch("aws_lambda_builders.workflows.ruby_bundler.bundler.SubprocessBundler")
    def test_unsupported_runtime_validation(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        validator = RubyRuntimeValidator(
            runtime="ruby2.4",
            bundler=subprocess_bundler
        )
        self.assertFalse(validator.validate(runtime_path=subprocess_bundler))

    @patch("aws_lambda_builders.workflows.ruby_bundler.bundler.SubprocessBundler")
    def test_runtime_validate_zero_exit(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0, out=b"")
            self.validator.validate(runtime_path=subprocess_bundler)
            self.assertTrue(mock_subprocess.call_count, 1)
            self.assertEqual("bundler", self.validator.validated_runtime_path)

    @patch("aws_lambda_builders.workflows.ruby_bundler.bundler.SubprocessBundler")
    def test_runtime_validate_mismatch_nonzero_exit(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        with mock.patch("subprocess.Popen") as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                self.validator.validate(runtime_path=subprocess_bundler)
                self.assertTrue(mock_subprocess.call_count, 1)
