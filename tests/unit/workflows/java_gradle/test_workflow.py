from unittest import TestCase

from aws_lambda_builders.workflows.java_gradle.workflow import JavaGradleWorkflow
from aws_lambda_builders.workflows.java_gradle.actions import JavaGradleBuildAction


class TestJavaGradleWorkflow(TestCase):
    """
    the workflow requires an external utility (gradle) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_gradle_actions(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertEqual(len(workflow.actions), 1)

        self.assertIsInstance(workflow.actions[0], JavaGradleBuildAction)
