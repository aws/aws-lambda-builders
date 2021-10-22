import mock
from mock import patch, ANY, Mock
from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction, CleanUpAction
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

    def test_workflow_sets_up_actions_without_download_dependencies_with_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
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
        osutils_mock = Mock(spec=self.osutils)
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
        self.assertEqual(len(self.workflow.actions), 4)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopySourceAction)
        self.assertIsInstance(self.workflow.actions[3], CopySourceAction)
        # check copying dependencies does not have any exclude
        self.assertEqual(self.workflow.actions[2].excludes, [])

    def test_workflow_sets_up_actions_without_download_dependencies_without_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.7",
            osutils=osutils_mock,
            dependencies_dir=None,
            download_dependencies=False,
        )
        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_sets_up_actions_without_combine_dependencies(self):
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
            combine_dependencies=False,
        )
        self.assertEqual(len(self.workflow.actions), 3)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopySourceAction)

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
            None,
            binaries=ANY,
            architecture="ARM64",
        )
        self.assertEqual(2, len(self.workflow.actions))
