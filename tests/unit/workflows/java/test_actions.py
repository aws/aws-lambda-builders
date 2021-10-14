from unittest import TestCase
from mock import patch
import os

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.java.actions import JavaCopyDependenciesAction, JavaMoveDependenciesAction


class TestJavaCopyDependenciesAction(TestCase):
    @patch("aws_lambda_builders.workflows.java.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value
        self.os_utils.copy.side_effect = lambda src, dst: dst
        self.artifacts_dir = "artifacts_dir"
        self.dependencies_dir = "dependencies_dir"

    def test_copies_artifacts(self):
        self.os_utils.copytree.side_effect = lambda src, dst: None
        self.os_utils.copy.side_effect = lambda src, dst: None

        action = JavaCopyDependenciesAction(self.artifacts_dir, self.dependencies_dir, self.os_utils)
        action.execute()

        self.os_utils.copytree.assert_called_with(
            os.path.join(self.artifacts_dir, "lib"), os.path.join(self.dependencies_dir, "lib")
        )

    def test_error_in_artifact_copy_raises_action_error(self):
        self.os_utils.copytree.side_effect = Exception("scandir failed!")
        action = JavaCopyDependenciesAction(self.artifacts_dir, self.dependencies_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "scandir failed!")


class TestJavaMoveDependenciesAction(TestCase):
    @patch("aws_lambda_builders.workflows.java.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value
        self.artifacts_dir = "artifacts_dir"
        self.dependencies_dir = "dependencies_dir"

    def test_copies_artifacts(self):
        self.os_utils.move.side_effect = lambda src, dst: None

        action = JavaMoveDependenciesAction(self.artifacts_dir, self.dependencies_dir, self.os_utils)
        action.execute()

        self.os_utils.move.assert_called_with(os.path.join(self.artifacts_dir, "lib"), self.dependencies_dir)

    def test_error_in_artifact_copy_raises_action_error(self):
        self.os_utils.move.side_effect = Exception("scandir failed!")
        action = JavaMoveDependenciesAction(self.artifacts_dir, self.dependencies_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "scandir failed!")
