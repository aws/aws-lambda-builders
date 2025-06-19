import os
import pathlib
import shutil
import sys
import platform
import tempfile
from unittest import TestCase, skipIf

from parameterized import parameterized_class

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.utils import which
from aws_lambda_builders.workflows.python_uv.utils import EXPERIMENTAL_FLAG_BUILD_PERFORMANCE

IS_WINDOWS = platform.system().lower() == "windows"


@parameterized_class(("experimental_flags",), [([]), ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE])])
class TestPythonUvWorkflow(TestCase):
    """
    Verifies that `python_uv` workflow works by building a Lambda with simple dependencies
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")
    experimental_flags = []

    def setUp(self):
        self.source_dir = self.TEST_DATA_FOLDER
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()

        self.manifest_path_requirements = os.path.join(self.TEST_DATA_FOLDER, "requirements-simple.txt")
        self.manifest_path_pyproject = os.path.join(self.TEST_DATA_FOLDER, "pyproject.toml")

        self.test_data_files = {
            "__init__.py",
            "main.py",
            "requirements-simple.txt",
            "pyproject.toml",
        }

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_uses_requirements_txt_file(self):
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_requirements,
            runtime="python3.9",
            experimental_flags=self.experimental_flags,
        )

        expected_files = self.test_data_files.union({"six.py", "six-1.16.0.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files.intersection(output_files), expected_files)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_uses_pyproject_toml_file(self):
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_pyproject,
            runtime="python3.9",
            experimental_flags=self.experimental_flags,
        )

        expected_files = self.test_data_files.union({"six.py", "six-1.16.0.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files.intersection(output_files), expected_files)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_with_dependencies_dir(self):
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_requirements,
            runtime="python3.9",
            dependencies_dir=self.dependencies_dir,
            experimental_flags=self.experimental_flags,
        )

        expected_files = self.test_data_files
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files.intersection(output_files), expected_files)

        expected_dependencies = {"six.py", "six-1.16.0.dist-info"}
        dependencies_files = set(os.listdir(self.dependencies_dir))
        self.assertEqual(expected_dependencies.intersection(dependencies_files), expected_dependencies)
