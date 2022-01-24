from unittest import TestCase
from parameterized import parameterized

from aws_lambda_builders.workflows.nodejs_npm.utils import EXPERIMENTAL_FLAG_ESBUILD, is_experimental_esbuild_scope


class TestNodejsUtils(TestCase):
    @parameterized.expand(
        [
            (None, False),
            ([], False),
            ([EXPERIMENTAL_FLAG_ESBUILD], True),
            ([EXPERIMENTAL_FLAG_ESBUILD, "SomeOtherFlag"], True),
        ]
    )
    def test_experimental_esbuild_scope_check(self, experimental_flags, expected):
        self.assertEqual(is_experimental_esbuild_scope(experimental_flags), expected)
