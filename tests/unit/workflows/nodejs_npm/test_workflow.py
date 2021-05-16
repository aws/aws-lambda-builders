from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmLockFileCleanUpAction
)


class TestNodejsNpmWorkflow(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value

    """
    the workflow requires an external utility (npm) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_npm_actions(self):

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 6)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)

        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)

        self.assertIsInstance(workflow.actions[2], CopySourceAction)

        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)

        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

        self.assertIsInstance(workflow.actions[5], NodejsNpmLockFileCleanUpAction)
