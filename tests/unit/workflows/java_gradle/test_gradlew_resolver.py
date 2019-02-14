from unittest import TestCase

from mock import patch
from parameterized import parameterized
from aws_lambda_builders.workflows.java_gradle.gradle_resolver import GradleResolver


class TestGradleResolver(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.mock_os_utils = MockOSUtils.return_value
        self.mock_os_utils.is_windows.side_effect = [False]

    def test_gradlew_exists_returns_gradlew(self):
        gradlew_path = '/path/to/gradlew'
        self.mock_os_utils.which.side_effect = lambda executable, executable_search_paths: [gradlew_path]

        resolver = GradleResolver(os_utils=self.mock_os_utils)
        self.assertEquals(resolver.exec_paths, [gradlew_path])

    def test_gradlew_not_exists_returns_gradle_on_path(self):
        gradle_path = '/path/to/gradle'
        self.mock_os_utils.which.side_effect = lambda executable, executable_search_paths: \
            [] if executable == 'gradlew' else [gradle_path]

        resolver = GradleResolver(os_utils=self.mock_os_utils)
        self.assertEquals(resolver.exec_paths, [gradle_path])

    def test_throws_value_error_if_no_exec_found(self):
        self.mock_os_utils.which.side_effect = lambda executable, executable_search_paths: []
        resolver = GradleResolver(os_utils=self.mock_os_utils)
        with self.assertRaises(ValueError) as raised:
            resolver.exec_paths()
        self.assertEquals(raised.exception.args[0], 'No Gradle executable found!')

    @parameterized.expand([
        [True, 'gradlew.bat'],
        [False, 'gradlew']
    ])
    def test_uses_correct_gradlew_name(self, is_windows, expected_wrapper_name):
        self.mock_os_utils.is_windows.side_effect = [is_windows]
        resolver = GradleResolver(os_utils=self.mock_os_utils)
        self.assertEquals(resolver.wrapper_name, expected_wrapper_name)
