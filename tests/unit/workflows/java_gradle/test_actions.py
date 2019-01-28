from unittest import TestCase
from mock import patch
import os

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.java_gradle.actions import JavaGradleBuildAction, GradleExecutionError


class TestJavaGradleBuildAction(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.java_gradle.gradle.SubprocessGradle")
    def setUp(self, MockSubprocessGradle, MockOSUtils):
        self.subprocess_gradle = MockSubprocessGradle.return_value
        self.os_utils = MockOSUtils.return_value
        self.os_utils.copy.side_effect = lambda src, dst: dst
        self.source_dir = "source_dir"
        self.artifacts_dir = "artifacts_dir"
        self.scratch_dir = "scratch_dir"

    def test_calls_gradle_build(self):
        action = JavaGradleBuildAction(self.source_dir, self.artifacts_dir, {}, self.subprocess_gradle,
                                       self.scratch_dir, self.os_utils)
        action.execute()
        self.subprocess_gradle.build.assert_called_with(self.source_dir,
                                                        os.path.join(self.scratch_dir,
                                                                     JavaGradleBuildAction.INIT_SCRIPT))

    def test_copies_artifacts(self):
        mapping = {'lambda1': 'artifact_lambda1', 'lambda2': 'artifact_lambda2'}
        self.os_utils.listdir.side_effect = lambda d: ['artifact.zip']

        action = JavaGradleBuildAction(self.source_dir, self.artifacts_dir, mapping, self.subprocess_gradle,
                                       self.scratch_dir, self.os_utils)
        action.execute()

        dist_dir = os.path.join('build', 'distributions', 'lambda-build')
        for l, a in mapping.items():
            self.os_utils.copy.assert_any_call(os.path.join(self.source_dir, l, dist_dir, 'artifact.zip'),
                                               os.path.join(self.artifacts_dir, a, 'artifact.zip'))

    def test_error_in_init_file_copy_raises_action_error(self):
        self.os_utils.copy.side_effect = Exception("Copy failed!")
        action = JavaGradleBuildAction(self.source_dir, self.artifacts_dir, {}, self.subprocess_gradle,
                                       self.scratch_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], "Copy failed!")

    def test_error_in_artifact_copy_raises_action_error(self):
        mapping = {'lambda1': 'artifact_lambda1', 'lambda2': 'artifact_lambda2'}
        self.os_utils.listdir.side_effect = Exception("listdir failed!")
        action = JavaGradleBuildAction(self.source_dir, self.artifacts_dir, mapping, self.subprocess_gradle,
                                       self.scratch_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], "listdir failed!")

    def test_error_building_project_raises_action_eror(self):
        self.subprocess_gradle.build.side_effect = GradleExecutionError(message='Build failed!')
        action = JavaGradleBuildAction(self.source_dir, self.artifacts_dir, {}, self.subprocess_gradle,
                                       self.scratch_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], 'Gradle Failed: Build failed!')
