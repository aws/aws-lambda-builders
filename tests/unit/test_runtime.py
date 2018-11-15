from unittest import TestCase

import mock

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.runtime import validate_python_cmd
from aws_lambda_builders.runtime import Runtime


class MockSubProcess(object):

    def __init__(self, returncode):
        self.returncode = returncode

    def communicate(self):
        pass


class TestRuntime(TestCase):

    def test_runtime_enums(self):
        self.assertTrue(Runtime.has_value("python2.7"))
        self.assertTrue(Runtime.has_value("python3.6"))
        self.assertFalse(Runtime.has_value("test_language"))

    def test_runtime_validate_unsupported_runtime(self):
        with self.assertRaises(ValueError):
            Runtime.validate_runtime("test_language", "test_language2.7")

    def test_runtime_validate_supported_version_runtime(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0)
            Runtime.validate_runtime("python", "python3.6")
            self.assertTrue(mock_subprocess.call_count, 1)

    def test_runtime_validate_mismatch_version_runtime(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            with self.assertRaises(MisMatchRuntimeError):
                Runtime.validate_runtime("python", "python2.7")
                self.assertTrue(mock_subprocess.call_count, 1)

    def test_python_command(self):
        cmd = validate_python_cmd("python", "python2.7")
        version_strings = ["sys.version_info.major == 2", "sys.version_info.minor == 7"]
        for version_string in version_strings:
            self.assertTrue(any([part for part in cmd if version_string in part]))
