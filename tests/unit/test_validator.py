from unittest import TestCase

from aws_lambda_builders.validator import RuntimeValidator


class TestRuntimeValidator(TestCase):

    def setUp(self):
        self.validator = RuntimeValidator(runtime="chitti2.0")

    def test_inits(self):
        self.assertEquals(self.validator.runtime, "chitti2.0")

    def test_validate_runtime(self):
        self.validator.validate("/usr/bin/chitti")
