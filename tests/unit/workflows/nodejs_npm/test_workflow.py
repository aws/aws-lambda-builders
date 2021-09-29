from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction, CopyDependenciesAction, MoveDependenciesAction
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcCopyAction,
    NodejsNpmrcCleanUpAction,
)


class TestNodejsNpmWorkflow(TestCase):

    """
    the workflow requires an external utility (npm) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir(self):

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)

        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)

        self.assertIsInstance(workflow.actions[2], CopySourceAction)

        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)

        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_with_dependencies_dir(self):

        workflow = NodejsNpmWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", download_dependencies=False
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_and_dependencies_dir(self):

        workflow = NodejsNpmWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", download_dependencies=True
        )

        self.assertEqual(len(workflow.actions), 7)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], MoveDependenciesAction)
        self.assertIsInstance(workflow.actions[5], CopySourceAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_and_without_dependencies_dir(self):

        workflow = NodejsNpmWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir=None, download_dependencies=False
        )

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_combine_dependencies(self):

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
        )

        self.assertEqual(len(workflow.actions), 6)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], MoveDependenciesAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)
