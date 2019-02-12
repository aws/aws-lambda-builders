from unittest import TestCase

from mock import patch
from aws_lambda_builders.workflows.java_gradle.gradlew_resolver import GradlewResolver


class TestGradleResolver(TestCase):

    def test_returns_dummy_if_executable_not_found(self):
        resolver = GradlewResolver('some-executable')
        self.assertIs(resolver.exec_paths[0], GradlewResolver.DUMMY_PATH)

    @patch("aws_lambda_builders.path_resolver.PathResolver")
    def test_does_not_suppress_non_path_resolver_errors(self, MockPathResolver):
        mock_path_resolver = MockPathResolver.return_value
        e = ValueError("Some other error!")
        mock_path_resolver.exec_paths.side_effect = e
        with self.assertRaises(ValueError) as raised:
            resolver = GradlewResolver('some-executable', path_resolver=mock_path_resolver)
            resolver.exec_paths()
        self.assertIs(raised.exception, e)
