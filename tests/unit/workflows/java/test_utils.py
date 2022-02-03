from unittest import TestCase

from parameterized import parameterized

from aws_lambda_builders.workflows.java.utils import (
    jar_file_filter,
    EXPERIMENTAL_MAVEN_SCOPE_AND_LAYER_FLAG,
    is_experimental_maven_scope_and_layers_active,
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

    @parameterized.expand(
        [
            (None, False),
            ([], False),
            ([EXPERIMENTAL_MAVEN_SCOPE_AND_LAYER_FLAG], True),
            ([EXPERIMENTAL_MAVEN_SCOPE_AND_LAYER_FLAG, "SomeOtherFlag"], True),
        ]
    )
    def test_experimental_maven_scope_and_layers_check(self, experimental_flags, expected):
        self.assertEqual(is_experimental_maven_scope_and_layers_active(experimental_flags), expected)
