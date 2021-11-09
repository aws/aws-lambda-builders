from unittest import TestCase
from mock import patch, call
import os

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.java_maven.actions import (
    JavaMavenBuildAction,
    JavaMavenCopyArtifactsAction,
    JavaMavenCopyDependencyAction,
    MavenExecutionError,
)


class TestJavaMavenBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.java_maven.maven.SubprocessMaven")
    def setUp(self, MockSubprocessMaven):
        self.subprocess_maven = MockSubprocessMaven.return_value
        self.scratch_dir = os.path.join("scratch_dir")
        self.artifacts_dir = os.path.join("artifacts_dir")

    def test_calls_maven_build(self):
        action = JavaMavenBuildAction(self.scratch_dir, self.subprocess_maven)
        action.execute()
        self.subprocess_maven.build.assert_called_with(self.scratch_dir)

    def test_error_building_project_raises_action_error(self):
        self.subprocess_maven.build.side_effect = MavenExecutionError(message="Build failed!")
        action = JavaMavenBuildAction(self.scratch_dir, self.subprocess_maven)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "Maven Failed: Build failed!")


class TestJavaMavenCopyDependencyAction(TestCase):
    @patch("aws_lambda_builders.workflows.java_maven.maven.SubprocessMaven")
    def setUp(self, MockSubprocessMaven):
        self.subprocess_maven = MockSubprocessMaven.return_value
        self.scratch_dir = os.path.join("scratch_dir")
        self.artifacts_dir = os.path.join("artifacts_dir")

    def test_calls_maven_copy_dependency(self):
        action = JavaMavenCopyDependencyAction(self.scratch_dir, self.subprocess_maven)
        action.execute()
        self.subprocess_maven.copy_dependency.assert_called_with(self.scratch_dir)

    def test_error_building_project_raises_action_error(self):
        self.subprocess_maven.copy_dependency.side_effect = MavenExecutionError(message="Build failed!")
        action = JavaMavenCopyDependencyAction(self.scratch_dir, self.subprocess_maven)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "Maven Failed: Build failed!")


class TestJavaMavenCopyArtifactsAction(TestCase):
    @patch("aws_lambda_builders.workflows.java.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value
        self.os_utils.copy.side_effect = lambda src, dst: dst
        self.scratch_dir = "scratch_dir"
        self.output_dir = os.path.join(self.scratch_dir, "target", "classes")
        self.artifacts_dir = os.path.join("artifacts_dir")

    def test_copies_artifacts_no_deps(self):
        self.os_utils.exists.return_value = True
        self.os_utils.copytree.side_effect = lambda src, dst: None
        self.os_utils.copy.side_effect = lambda src, dst: None

        action = JavaMavenCopyArtifactsAction(self.scratch_dir, self.artifacts_dir, self.os_utils)
        action.execute()

        self.os_utils.copytree.assert_has_calls(
            [call(os.path.join(self.scratch_dir, "target", "classes"), self.artifacts_dir)]
        )

    def test_copies_artifacts_with_deps(self):
        self.os_utils.exists.return_value = True
        self.os_utils.copytree.side_effect = lambda src, dst: None
        self.os_utils.copy.side_effect = lambda src, dst: None
        os.path.join(self.scratch_dir, "target", "dependency")

        action = JavaMavenCopyArtifactsAction(self.scratch_dir, self.artifacts_dir, self.os_utils)
        action.execute()
        self.os_utils.copytree.assert_has_calls(
            [
                call(os.path.join(self.scratch_dir, "target", "classes"), self.artifacts_dir),
                call(os.path.join(self.scratch_dir, "target", "dependency"), os.path.join(self.artifacts_dir, "lib")),
            ]
        )

    def test_error_in_artifact_copy_raises_action_error(self):
        self.os_utils.exists.return_value = True
        self.os_utils.copytree.side_effect = Exception("copy failed!")
        action = JavaMavenCopyArtifactsAction(self.scratch_dir, self.artifacts_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "copy failed!")

    def test_missing_required_target_class_directory_raises_action_error(self):
        self.os_utils.exists.return_value = False
        action = JavaMavenCopyArtifactsAction(self.scratch_dir, self.artifacts_dir, self.os_utils)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(
            raised.exception.args[0], "Required target/classes directory was not " "produced from 'mvn package'"
        )
