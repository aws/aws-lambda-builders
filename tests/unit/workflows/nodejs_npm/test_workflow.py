from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import NodejsNpmPackAction, NodejsNpmInstallAction


class TestNodejsNpmWorkflow(TestCase):

    """
    the workflow requires an external utility (npm) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_npm_actions(self):

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertEqual(len(workflow.actions), 3)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)

        self.assertIsInstance(workflow.actions[1], CopySourceAction)

        self.assertIsInstance(workflow.actions[2], NodejsNpmInstallAction)
