import mock

from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction, CopyDependenciesAction, MoveDependenciesAction, CleanUpAction
from aws_lambda_builders.architecture import ARM64
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcCopyAction,
    NodejsNpmrcCleanUpAction,
)
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils


class TestNodejsNpmWorkflow(TestCase):

    """
    the workflow requires an external utility (npm) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def setUp(self):
        self.osutils_mock = mock.Mock(spec=OSUtils())

    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir(self):

        self.osutils_mock.file_exists.return_value = True

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils_mock)

        self.assertEqual(len(workflow.actions), 5)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_with_dependencies_dir(self):

        self.osutils_mock.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir="dep",
            download_dependencies=False,
            osutils=self.osutils_mock,
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_and_dependencies_dir(self):

        self.osutils_mock.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            osutils=self.osutils_mock,
        )

        self.assertEqual(len(workflow.actions), 7)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], CleanUpAction)
        self.assertIsInstance(workflow.actions[5], CopyDependenciesAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_and_without_dependencies_dir(self):

        self.osutils_mock.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir=None,
            download_dependencies=False,
            osutils=self.osutils_mock,
        )

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_combine_dependencies(self):

        self.osutils_mock.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
            osutils=self.osutils_mock,
        )

        self.assertEqual(len(workflow.actions), 7)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], CleanUpAction)
        self.assertIsInstance(workflow.actions[5], MoveDependenciesAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)

    def test_workflow_only_copy_action(self):
        self.osutils_mock.file_exists.return_value = False

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils_mock)

        self.assertEqual(len(workflow.actions), 1)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

    def test_must_validate_architecture(self):
        self.osutils_mock.file_exists.return_value = True
        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
            osutils=self.osutils_mock,
        )
        workflow_with_arm = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
            architecture=ARM64,
            osutils=self.osutils_mock,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")
