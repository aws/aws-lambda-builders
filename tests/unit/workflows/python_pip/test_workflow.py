from mock import patch, ANY, Mock
from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.python_pip.utils import OSUtils
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator
from aws_lambda_builders.workflows.python_pip.workflow import PythonPipBuildAction, PythonPipWorkflow


class TestPythonPipWorkflow(TestCase):
    def setUp(self):
        self.osutils = OSUtils()
        self.osutils_mock = Mock(spec=self.osutils)
        self.osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", runtime="python3.7", osutils=self.osutils_mock
        )

    def test_workflow_sets_up_actions(self):
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_without_requirements(self):
        self.osutils_mock.file_exists.return_value = False
        self.workflow = PythonPipWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", runtime="python3.7", osutils=self.osutils_mock
        )
        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_validator(self):
        for validator in self.workflow.get_validators():
            self.assertTrue(isinstance(validator, PythonRuntimeValidator))

    @patch("aws_lambda_builders.workflows.python_pip.workflow.PythonPipBuildAction")
    def test_must_build_with_architecture(self, PythonPipBuildActionMock):
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.7",
            architecture="ARM64",
            osutils=self.osutils_mock,
        )
        PythonPipBuildActionMock.assert_called_with(
            "artifacts",
            "scratch_dir",
            "manifest",
            "python3.7",
            binaries=ANY,
            architecture="ARM64",
        )
        self.assertEqual(2, len(self.workflow.actions))
