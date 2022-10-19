import mock
from mock import patch, ANY, Mock
from unittest import TestCase

from parameterized import parameterized_class

from aws_lambda_builders.actions import CopySourceAction, CleanUpAction, LinkSourceAction
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflows.python_pip.utils import OSUtils, EXPERIMENTAL_FLAG_BUILD_PERFORMANCE
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator
from aws_lambda_builders.workflows.python_pip.workflow import PythonPipBuildAction, PythonPipWorkflow


@parameterized_class(
    ("experimental_flags",),
    [
        ([]),
        ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE]),
    ],
)
class TestPythonPipWorkflow(TestCase):
    experimental_flags = []

    def setUp(self):
        self.osutils = OSUtils()
        self.osutils_mock = Mock(spec=self.osutils)
        self.osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )
        self.python_major_version = "3"
        self.python_minor_version = "9"
        self.language = "python"

    def test_workflow_sets_up_actions(self):
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_without_requirements(self):
        self.osutils_mock.file_exists.return_value = False
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )
        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_validator(self):
        for validator in self.workflow.get_validators():
            self.assertTrue(isinstance(validator, PythonRuntimeValidator))

    def test_workflow_resolver(self):
        for resolver in self.workflow.get_resolvers():
            self.assertTrue(isinstance(resolver, PathResolver))
            self.assertTrue(
                resolver.executables,
                [
                    self.language,
                    f"{self.language}{self.python_major_version}.{self.python_minor_version}",
                    f"{self.language}{self.python_major_version}",
                ],
            )

    def test_workflow_sets_up_actions_without_download_dependencies_with_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
        )
        self.assertEqual(len(self.workflow.actions), 2)
        # symlinking python dependencies is disabled for now since it is breaking sam local commands
        if False and self.experimental_flags:
            self.assertIsInstance(self.workflow.actions[0], LinkSourceAction)
        else:
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
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=True,
            experimental_flags=self.experimental_flags,
        )
        self.assertEqual(len(self.workflow.actions), 4)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonPipBuildAction)
        # symlinking python dependencies is disabled for now since it is breaking sam local commands
        if False and self.experimental_flags:
            self.assertIsInstance(self.workflow.actions[2], LinkSourceAction)
        else:
            self.assertIsInstance(self.workflow.actions[2], CopySourceAction)
            # check copying dependencies does not have any exclude
            self.assertEqual(self.workflow.actions[2].excludes, [])
        self.assertIsInstance(self.workflow.actions[3], CopySourceAction)

    def test_workflow_sets_up_actions_without_download_dependencies_without_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir=None,
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
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
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
            experimental_flags=self.experimental_flags,
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
            runtime="python3.9",
            architecture="ARM64",
            osutils=self.osutils_mock,
        )
        PythonPipBuildActionMock.assert_called_with(
            "artifacts",
            "scratch_dir",
            "manifest",
            "python3.9",
            None,
            binaries=ANY,
            architecture="ARM64",
        )
        self.assertEqual(2, len(self.workflow.actions))
