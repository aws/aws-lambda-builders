from unittest import TestCase
from mock import patch
import os

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.java.actions import JavaCopyDependenciesAction


class TestJavaCopyDependenciesAction(TestCase):
    @patch("aws_lambda_builders.workflows.java.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value
        self.os_utils.copy.side_effect = lambda src, dst: dst
        self.source_dir = "source_dir"
        self.artifacts_dir = "artifacts_dir"
        self.scratch_dir = "scratch_dir"
        self.build_dir = os.path.join(self.scratch_dir, "build1")

    def test_copies_artifacts(self):
        self.os_utils.copytree.side_effect = lambda src, dst: None
        self.os_utils.copy.side_effect = lambda src, dst: None

        action = JavaCopyDependenciesAction(self.source_dir, self.artifacts_dir, self.build_dir, self.os_utils)
        action.execute()

        self.os_utils.copytree.assert_called_with(
            os.path.join(self.build_dir, "build", "distributions", "lambda-build"), self.artifacts_dir
        )

    def test_error_in_artifact_copy_raises_action_error(self):
        self.os_utils.copytree.side_effect = Exception("scandir failed!")
        action = JavaCopyDependenciesAction(self.source_dir, self.artifacts_dir, self.build_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "scandir failed!")
