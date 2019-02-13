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


class FakeDirEntry(object):
    def __init__(self, path=None, is_dir=False, name=None):
        self.path = path
        self._is_dir = is_dir
        self.name = name

    def is_dir(self):
        return self._is_dir


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
        resource_path = os.path.join('someresource.txt')
        classes_path = os.path.join('path', 'to', 'com')
        lib_path = os.path.join('path', 'to', 'lib')
        self.os_utils.scandir.side_effect = lambda d: [FakeDirEntry(path=classes_path, is_dir=True, name='com'),
                                                       FakeDirEntry(path=lib_path, is_dir=True, name='lib'),
                                                       FakeDirEntry(resource_path, name='someresource.txt')]

        action = JavaGradleCopyArtifactsAction(self.source_dir,
                                               self.artifacts_dir,
                                               self.build_dir,
                                               self.os_utils)
        action.execute()

        self.os_utils.copytree.assert_any_call(classes_path, os.path.join(self.artifacts_dir, 'com'))
        self.os_utils.copytree.assert_any_call(lib_path, os.path.join(self.artifacts_dir, 'lib'))
        self.os_utils.copy.assert_any_call(resource_path, os.path.join(self.artifacts_dir, 'someresource.txt'))

    def test_error_in_artifact_copy_raises_action_error(self):
        self.os_utils.scandir.side_effect = Exception("scandir failed!")
        action = JavaGradleCopyArtifactsAction(self.source_dir,
                                               self.artifacts_dir,
                                               self.build_dir,
                                               self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEquals(raised.exception.args[0], "scandir failed!")
