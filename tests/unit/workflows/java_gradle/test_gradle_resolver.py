import os
from unittest import TestCase
from mock import patch
from parameterized import parameterized

from aws_lambda_builders.workflows.java_gradle.gradle_resolver import GradleResolver


class TestGradleResolver(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.mock_os_utils = MockOSUtils.return_value


    @parameterized.expand([
        [True],
        [False]
    ])
    def test_returns_gradlew_if_found_in_source_dir(self, is_windows):
        self.mock_os_utils.exists.side_effect = [True]
        self.mock_os_utils.is_windows.side_effect = lambda: is_windows
        source_dir = os.path.join('src')
        resolver = GradleResolver(source_dir, self.mock_os_utils)
        gradle = 'gradlew.bat' if is_windows else 'gradlew'
        self.assertEquals([os.path.join(source_dir, gradle)], resolver.exec_paths)
