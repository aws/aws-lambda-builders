import mock

from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.python_pip.utils import OSUtils
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator
from aws_lambda_builders.workflows.python_pip.workflow import PythonPipBuildAction, PythonPipWorkflow


class TestPythonPipWorkflow(TestCase):
    def setUp(self):
        self.osutils = OSUtils()

    def test_workflow_sets_up_actions(self):
        osutils_mock = mock.Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", runtime="python3.7", osutils=osutils_mock
        )
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_without_requirements(self):
        osutils_mock = mock.Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = False
        self.workflow = PythonPipWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", runtime="python3.7", osutils=osutils_mock
        )
        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_validator(self):
        self.workflow = PythonPipWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="python3.7")
        for validator in self.workflow.get_validators():
            self.assertTrue(isinstance(validator, PythonRuntimeValidator))

    def test_workflow_sets_up_actions_without_download_dependencies(self):
        osutils_mock = mock.Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.7",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=False,
        )
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_with_download_dependencies_and_dependencies_dir(self):
        osutils_mock = mock.Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.7",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=True,
        )
        self.assertEqual(len(self.workflow.actions), 3)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)
        self.assertIsInstance(self.workflow.actions[2], CopySourceAction)
