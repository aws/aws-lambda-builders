from unittest import TestCase

from mock import patch
from aws_lambda_builders.workflows.java_maven.maven_resolver import MavenResolver


class TestMavenResolver(TestCase):
    @patch("aws_lambda_builders.workflows.java.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.mock_os_utils = MockOSUtils.return_value
        self.mock_os_utils.is_windows.side_effect = [False]

    def test_returns_maven_on_path(self):
        maven_path = "/path/to/mvn"
        self.mock_os_utils.which.side_effect = lambda executable, executable_search_paths: [maven_path]

        resolver = MavenResolver(os_utils=self.mock_os_utils)
        self.assertEqual(resolver.exec_paths, [maven_path])

    def test_throws_value_error_if_no_exec_found(self):
        self.mock_os_utils.which.side_effect = lambda executable, executable_search_paths: []
        resolver = MavenResolver(os_utils=self.mock_os_utils)
        with self.assertRaises(ValueError) as raised:
            resolver.exec_paths()
        self.assertEqual(raised.exception.args[0], "No Maven executable found!")
