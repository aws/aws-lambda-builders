import sys

from unittest import TestCase
import mock

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator


class MockSubProcess(object):

    def __init__(self, returncode):
        self.returncode = returncode

    def communicate(self):
        pass


class TestPythonRuntimeValidator(TestCase):

    def setUp(self):
        self.runtime_validator = PythonRuntimeValidator("python3.6")

    def test_python_validator_inits(self):
        self.assertEquals(self.runtime_validator.SUPPORTED_RUNTIMES,
                          ["python2.7","python3.6"])
        self.assertEquals(self.runtime_validator.language, "python")
        self.assertEquals(self.runtime_validator.language_runtime, "python3.6")

    def test_python_valid_runtimes(self):
        self.assertTrue(self.runtime_validator.has_runtime())

    def test_python_invalid_runtime(self):
        runtime_validator = PythonRuntimeValidator("python2.8")
        self.assertFalse(runtime_validator.has_runtime())

    def test_python_valid_runtime_path(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(0)
            runtime_validator = PythonRuntimeValidator("python{}.{}".format(sys.version_info.major, sys.version_info.minor))
            runtime_validator.validate_runtime(sys.executable)

    def test_python_invalid_runtime_path(self):
        with mock.patch('subprocess.Popen') as mock_subprocess:
            mock_subprocess.return_value = MockSubProcess(1)
            runtime_validator = PythonRuntimeValidator("python{}.{}".format(sys.version_info.major, sys.version_info.minor))
            with self.assertRaises(MisMatchRuntimeError):
                runtime_validator.validate_runtime(sys.executable)

