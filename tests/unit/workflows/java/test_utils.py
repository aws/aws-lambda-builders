from unittest import TestCase

from parameterized import parameterized

from aws_lambda_builders.workflows.java.utils import (
    jar_file_filter,
)


class TestJavaUtils(TestCase):
    @parameterized.expand(
        [
            (None, False),
            (123, False),
            ("not_a_jar_file.txt", False),
            ("jar_file.jar", True),
        ]
    )
    def test_jar_file_filter(self, file_name, expected):
        self.assertEqual(jar_file_filter(file_name), expected)
