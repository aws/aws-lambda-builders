from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator
from aws_lambda_builders.workflows.python_pip.workflow import PythonPipBuildAction, PythonPipWorkflow


class TestPythonPipWorkflow(TestCase):

    def setUp(self):
        self.workflow = PythonPipWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="python3.7")

    def test_workflow_sets_up_actions(self):
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_validator(self):
        for validator in self.workflow.get_validators():
            self.assertTrue(isinstance(validator, PythonRuntimeValidator))
