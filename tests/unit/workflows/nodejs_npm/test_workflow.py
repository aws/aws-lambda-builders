
from unittest import TestCase

from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow

from aws_lambda_builders.workflows.nodejs_npm.actions import NodejsNpmPackAction, NodejsNpmInstallAction

from aws_lambda_builders.actions import CopySourceAction


class TestNodejsNpmWorkflow(TestCase):

    """
    the workflow requires an external utility (npm) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_npm_actions(self):

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest")

        assert len(workflow.actions) == 3

        assert isinstance(workflow.actions[0], NodejsNpmPackAction)

        assert isinstance(workflow.actions[1], CopySourceAction)

        assert isinstance(workflow.actions[2], NodejsNpmInstallAction)
