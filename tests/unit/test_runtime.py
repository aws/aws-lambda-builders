from unittest import TestCase

import mock

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.validate import validate_python_cmd
from aws_lambda_builders.validate import RuntimeValidator


class MockSubProcess(object):

    def __init__(self, returncode):
        self.returncode = returncode

    def communicate(self):
        pass


class TestRuntime(TestCase):

    def test_supported_runtimes(self):
        self.assertTrue(RuntimeValidator.has_runtime("python2.7"))
        self.assertTrue(RuntimeValidator.has_runtime("python3.6"))
        self.assertFalse(RuntimeValidator.has_runtime("test_language"))

    def test_runtime_validate_unsupported_language_fail_open(self):
        RuntimeValidator.validate_runtime("test_language", "test_language2.7")

    def test_runtime_validate_unsupported_runtime_version_fail_open(self):
        RuntimeValidator.validate_runtime("python", "python2.8")

    def test_runtime_validate_supported_version_runtime(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0)
            RuntimeValidator.validate_runtime("python", "python3.6")
            self.assertTrue(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_version_runtime(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                RuntimeValidator.validate_runtime("python", "python2.7")
                self.assertTrue(mock_subprocess.call_count, 1)

    def test_python_command(self):
        cmd = validate_python_cmd("python", "python2.7")
        version_strings = ["sys.version_info.major == 2", "sys.version_info.minor == 7"]
        for version_string in version_strings:
            self.assertTrue(any([part for part in cmd if version_string in part]))
