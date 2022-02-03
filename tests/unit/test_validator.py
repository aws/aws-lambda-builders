from unittest import TestCase

from aws_lambda_builders.validator import RuntimeValidator
from aws_lambda_builders.exceptions import UnsupportedRuntimeError, UnsupportedArchitectureError


class TestRuntimeValidator(TestCase):
    def setUp(self):
        self.validator = RuntimeValidator(runtime="python3.8", architecture="arm64")

    def test_inits(self):
        self.assertEqual(self.validator.runtime, "python3.8")
        self.assertEqual(self.validator.architecture, "arm64")

    def test_validate_runtime(self):
        self.validator.validate("/usr/bin/python3.8")
        self.assertEqual(self.validator._runtime_path, "/usr/bin/python3.8")

    def test_validate_with_unsupported_runtime(self):
        validator = RuntimeValidator(runtime="unknown_runtime", architecture="x86_64")
        with self.assertRaises(UnsupportedRuntimeError):
            validator.validate("/usr/bin/unknown_runtime")

    def test_validate_with_runtime_and_incompatible_architecture(self):
        runtime_list = ["dotnetcore2.1", "nodejs10.x", "ruby2.5", "python3.6", "python3.7", "python2.7"]
        for runtime in runtime_list:
            validator = RuntimeValidator(runtime=runtime, architecture="arm64")
            with self.assertRaises(UnsupportedArchitectureError):
                validator.validate("/usr/bin/{}".format(runtime))
