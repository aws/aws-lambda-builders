from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.provided_make.workflow import ProvidedMakeWorkflow
from aws_lambda_builders.workflows.provided_make.actions import ProvidedMakeAction


class TestProvidedMakeWorkflow(TestCase):

    """
    the workflow requires an external utility (make) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_make_actions(self):

        workflow = ProvidedMakeWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

        self.assertIsInstance(workflow.actions[1], ProvidedMakeAction)
