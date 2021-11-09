from unittest import TestCase

from aws_lambda_builders.architecture import X86_64, ARM64
from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.workflows.custom_make.workflow import CustomMakeWorkflow
from aws_lambda_builders.workflows.custom_make.actions import CustomMakeAction


class TestProvidedMakeWorkflow(TestCase):

    """
    the workflow requires an external utility (make) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_make_actions(self):

        workflow = CustomMakeWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", options={"build_logical_id": "hello"}
        )

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

        self.assertIsInstance(workflow.actions[1], CustomMakeAction)

    def test_workflow_sets_up_make_actions_no_options(self):

        with self.assertRaises(WorkflowFailedError):
            CustomMakeWorkflow("source", "artifacts", "scratch_dir", "manifest")

    def test_must_validate_architecture(self):
        workflow = CustomMakeWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", options={"build_logical_id": "hello"}
        )
        workflow_with_arm = CustomMakeWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            options={"build_logical_id": "hello"},
            architecture=ARM64,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")
