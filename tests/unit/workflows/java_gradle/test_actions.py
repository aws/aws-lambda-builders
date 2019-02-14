from unittest import TestCase
from mock import patch
import os

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.java_gradle.actions import JavaGradleBuildAction, JavaGradleCopyArtifactsAction, \
    GradleExecutionError


class TestJavaGradleBuildAction(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.java_gradle.gradle.SubprocessGradle")
    def setUp(self, MockSubprocessGradle, MockOSUtils):
        self.subprocess_gradle = MockSubprocessGradle.return_value
        self.os_utils = MockOSUtils.return_value
        self.os_utils.copy.side_effect = lambda src, dst: dst
        self.source_dir = os.path.join('source_dir')
        self.manifest_path = os.path.join(self.source_dir, 'manifest')
        self.artifacts_dir = os.path.join('artifacts_dir')
        self.scratch_dir = os.path.join('scratch_dir')

    def test_calls_gradle_build(self):
        action = JavaGradleBuildAction(self.source_dir,
                                       self.manifest_path,
                                       self.subprocess_gradle,
                                       self.scratch_dir,
                                       self.os_utils)
        action.execute()
        self.subprocess_gradle.build.assert_called_with(self.source_dir,
                                                        self.manifest_path,
                                                        os.path.join(self.scratch_dir,
                                                                     JavaGradleBuildAction.GRADLE_CACHE_DIR_NAME),
                                                        os.path.join(self.scratch_dir,
                                                                     JavaGradleBuildAction.INIT_SCRIPT),
                                                        {JavaGradleBuildAction.SCRATCH_DIR_PROPERTY: os.path.abspath(
                                                            self.scratch_dir)})

    def test_error_in_init_file_copy_raises_action_error(self):
        self.os_utils.copy.side_effect = Exception("Copy failed!")
        action = JavaGradleBuildAction(self.source_dir,
                                       self.manifest_path,
                                       self.subprocess_gradle,
                                       self.scratch_dir,
                                       self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], "Copy failed!")

    def test_error_building_project_raises_action_error(self):
        self.subprocess_gradle.build.side_effect = GradleExecutionError(message='Build failed!')
        action = JavaGradleBuildAction(self.source_dir,
                                       self.manifest_path,
                                       self.subprocess_gradle,
                                       self.scratch_dir,
                                       self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], 'Gradle Failed: Build failed!')

    def test_computes_correct_cache_dir(self):
        action = JavaGradleBuildAction(self.source_dir,
                                       self.manifest_path,
                                       self.subprocess_gradle,
                                       self.scratch_dir,
                                       self.os_utils)
        self.assertEquals(action.gradle_cache_dir,
                          os.path.join(self.scratch_dir, JavaGradleBuildAction.GRADLE_CACHE_DIR_NAME))


class TestJavaGradleCopyArtifactsAction(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value
        self.os_utils.copy.side_effect = lambda src, dst: dst
        self.source_dir = "source_dir"
        self.artifacts_dir = "artifacts_dir"
        self.scratch_dir = "scratch_dir"
        self.build_dir = os.path.join(self.scratch_dir, 'build1')

    def test_copies_artifacts(self):
        self.os_utils.copytree.side_effect = lambda src, dst: None
        self.os_utils.copy.side_effect = lambda src, dst: None

        action = JavaGradleCopyArtifactsAction(self.source_dir,
                                               self.artifacts_dir,
                                               self.build_dir,
                                               self.os_utils)
        action.execute()

        self.os_utils.copytree.assert_called_with(
            os.path.join(self.build_dir, 'build', 'distributions', 'lambda-build'), self.artifacts_dir)

    def test_error_in_artifact_copy_raises_action_error(self):
        self.os_utils.copytree.side_effect = Exception("scandir failed!")
        action = JavaGradleCopyArtifactsAction(self.source_dir,
                                               self.artifacts_dir,
                                               self.build_dir,
                                               self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], "scandir failed!")
