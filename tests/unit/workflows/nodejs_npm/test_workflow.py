import mock

from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
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

    def test_workflow_sets_up_npm_actions(self):

        self.osutils_mock.file_exists.return_value = True

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils_mock)

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)

        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)

        self.assertIsInstance(workflow.actions[2], CopySourceAction)

        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)

        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    def test_workflow_only_copy_action(self):
        self.osutils_mock.file_exists.return_value = False

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils_mock)

        self.assertEqual(len(workflow.actions), 1)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)
