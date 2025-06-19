from unittest import TestCase
from unittest.mock import patch, ANY, Mock

from parameterized import parameterized_class

from aws_lambda_builders.actions import CopySourceAction, CleanUpAction, LinkSourceAction
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflows.python_uv.utils import OSUtils, EXPERIMENTAL_FLAG_BUILD_PERFORMANCE
from aws_lambda_builders.workflows.python_uv.workflow import PythonUvWorkflow
from aws_lambda_builders.workflows.python_uv.actions import PythonUvBuildAction, CopyDependenciesAction


@parameterized_class(
    ("experimental_flags",),
    [
        ([]),
        ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE]),
    ],
)
class TestPythonUvWorkflow(TestCase):
    experimental_flags = []

    def setUp(self):
        self.osutils = OSUtils()
        self.osutils_mock = Mock(spec=self.osutils)
        self.osutils_mock.file_exists.return_value = True
        self.workflow = PythonUvWorkflow(
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
        self.assertIsInstance(self.workflow.actions[0], PythonUvBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_without_requirements(self):
        self.osutils_mock.file_exists.return_value = False
        self.workflow = PythonUvWorkflow(
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

    def test_workflow_sets_up_actions_with_dependencies_dir(self):
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            dependencies_dir="deps",
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 4)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonUvBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopyDependenciesAction)
        self.assertIsInstance(self.workflow.actions[3], CopySourceAction)

    def test_workflow_sets_up_actions_without_download_dependencies_and_dependencies_dir(self):
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_sets_up_actions_without_combine_dependencies(self):
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            dependencies_dir="deps",
            combine_dependencies=False,
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 3)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonUvBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopySourceAction)

    def test_workflow_name(self):
        self.assertEqual(self.workflow.NAME, "PythonUvBuilder")

    def test_workflow_capability(self):
        self.assertEqual(self.workflow.CAPABILITY.language, "python")
        self.assertEqual(self.workflow.CAPABILITY.dependency_manager, "uv")
        self.assertEqual(self.workflow.CAPABILITY.application_framework, None)

    def test_workflow_excluded_files(self):
        expected_excluded_files = (
            ".aws-sam",
            ".chalice",
            ".git",
            ".gitignore",
            "*.pyc",
            "__pycache__",
            "*.so",
            ".Python",
            "*.egg-info",
            "*.egg",
            "pip-log.txt",
            "pip-delete-this-directory.txt",
            "htmlcov",
            ".tox",
            ".nox",
            ".coverage",
            ".cache",
            ".pytest_cache",
            ".python-version",
            ".mypy_cache",
            ".dmypy.json",
            ".pyre",
            ".env",
            ".venv",
            "venv",
            "venv.bak",
            "env.bak",
            "ENV",
            "env",
            ".uv-cache",
            "uv.lock.bak",
            ".vscode",
            ".idea",
        )
        self.assertEqual(self.workflow.EXCLUDED_FILES, expected_excluded_files)

    def test_get_resolvers(self):
        resolvers = self.workflow.get_resolvers()
        self.assertEqual(len(resolvers), 1)
        self.assertIsInstance(resolvers[0], PathResolver)

    def test_get_validators(self):
        validators = self.workflow.get_validators()
        # UV has built-in Python version handling, no external validators needed
        self.assertEqual(len(validators), 0)

    @patch("aws_lambda_builders.workflows.python_uv.workflow.detect_uv_manifest")
    def test_workflow_auto_detects_manifest(self, mock_detect):
        mock_detect.return_value = "/path/to/pyproject.toml"
        self.osutils_mock.file_exists.return_value = False  # Original manifest doesn't exist

        workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "nonexistent_manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )

        mock_detect.assert_called_once_with("source")
        # Should have UV build action since manifest was detected
        self.assertEqual(len(workflow.actions), 2)
        self.assertIsInstance(workflow.actions[0], PythonUvBuildAction)
