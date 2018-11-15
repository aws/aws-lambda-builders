from unittest import TestCase

from aws_lambda_builders.workflows.python_pip.runtime_validator import validate_python_cmd


class TestPythonRuntimeValidator(TestCase):

    def test_python_command(self):
        cmd = validate_python_cmd("python", "python2.7")
        version_strings = ["sys.version_info.major == 2", "sys.version_info.minor == 7"]
        for version_string in version_strings:
            self.assertTrue(any([part for part in cmd if version_string in part]))
