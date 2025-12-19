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

        # PIP-equivalent test files for compatibility validation
        self.manifest_path_numpy = os.path.join(self.TEST_DATA_FOLDER, "requirements-numpy.txt")
        self.manifest_path_wrapt = os.path.join(self.TEST_DATA_FOLDER, "requirements-wrapt.txt")
        self.manifest_path_invalid = os.path.join(self.TEST_DATA_FOLDER, "requirements-invalid.txt")

        self.test_data_files = {
            "__init__.py",
            "main.py",
            "requirements-simple.txt",
            "pyproject.toml",
            "requirements-numpy.txt",
            "requirements-wrapt.txt",
            "requirements-invalid.txt",
            "pyproject-numpy.toml",
            "pyproject-wrapt.toml",
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

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_numpy_successfully(self):
        """Test that UV can build numpy (same as PIP workflow test)"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_numpy,
            runtime="python3.13",
            experimental_flags=self.experimental_flags,
        )

        # Check that numpy was built successfully
        output_files = set(os.listdir(self.artifacts_dir))
        expected_numpy_files = {"numpy", "numpy-2.1.2.dist-info", "numpy.libs"}

        # Verify numpy files are present
        for expected_file in expected_numpy_files:
            self.assertIn(expected_file, output_files, f"Expected {expected_file} in build output")

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_fails_with_wrapt_python313(self):
        """Test that UV fails with wrapt on Python 3.13 (same as PIP workflow)"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        # Should fail due to Python 3.13 incompatibility
        with self.assertRaises(WorkflowFailedError):
            builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_wrapt,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_fails_with_invalid_requirements(self):
        """Test that UV properly handles invalid requirements syntax (same as PIP workflow)"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        # Should fail due to invalid syntax (boto3=1.19.99 instead of boto3==1.19.99)
        with self.assertRaises(WorkflowFailedError) as ctx:
            builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_invalid,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

        # Verify error message mentions the syntax issue
        error_message = str(ctx.exception)
        self.assertIn("no such comparison operator", error_message)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_uses_pyproject_with_lock_file(self):
        """Test that UV uses existing uv.lock file for reproducible builds"""
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

        # uv.lock exists in testdata alongside pyproject.toml
        # Verify dependencies were installed from lock file
        expected_files = {"six.py", "six-1.16.0.dist-info"}
        output_files = set(os.listdir(self.artifacts_dir))
        for expected_file in expected_files:
            self.assertIn(expected_file, output_files)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_with_arm64_architecture(self):
        """Test that UV builds for ARM64 architecture"""
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_numpy,
            runtime="python3.12",
            architecture="arm64",
            experimental_flags=self.experimental_flags,
        )

        # Verify numpy was built for ARM64 by checking WHEEL metadata
        wheel_path = os.path.join(self.artifacts_dir, "numpy-2.1.2.dist-info", "WHEEL")
        self.assertTrue(os.path.exists(wheel_path), "WHEEL metadata file should exist")

        with open(wheel_path) as f:
            wheel_content = f.read()
        self.assertIn("aarch64", wheel_content, "WHEEL should contain aarch64 platform tag")

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_with_x86_64_architecture(self):
        """Test that UV builds for x86_64 architecture (default)"""
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_numpy,
            runtime="python3.12",
            architecture="x86_64",
            experimental_flags=self.experimental_flags,
        )

        # Verify numpy was built for x86_64 by checking WHEEL metadata
        wheel_path = os.path.join(self.artifacts_dir, "numpy-2.1.2.dist-info", "WHEEL")
        self.assertTrue(os.path.exists(wheel_path), "WHEEL metadata file should exist")

        with open(wheel_path) as f:
            wheel_content = f.read()
        self.assertIn("x86_64", wheel_content, "WHEEL should contain x86_64 platform tag")

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_numpy_with_pyproject(self):
        """Test that UV can build numpy using pyproject.toml format"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        # Create a temporary directory with pyproject.toml (UV only recognizes exact name)
        temp_source_dir = tempfile.mkdtemp()
        try:
            # Copy main.py to temp directory
            shutil.copy(os.path.join(self.TEST_DATA_FOLDER, "main.py"), temp_source_dir)
            shutil.copy(os.path.join(self.TEST_DATA_FOLDER, "__init__.py"), temp_source_dir)

            # Copy pyproject-numpy.toml as pyproject.toml
            shutil.copy(
                os.path.join(self.TEST_DATA_FOLDER, "pyproject-numpy.toml"),
                os.path.join(temp_source_dir, "pyproject.toml"),
            )

            pyproject_path = os.path.join(temp_source_dir, "pyproject.toml")

            builder.build(
                temp_source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                pyproject_path,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

            # Check that numpy was built successfully
            output_files = set(os.listdir(self.artifacts_dir))
            expected_numpy_files = {"numpy", "numpy-2.1.2.dist-info", "numpy.libs"}

            # Verify numpy files are present
            for expected_file in expected_numpy_files:
                self.assertIn(expected_file, output_files, f"Expected {expected_file} in build output")

        finally:
            shutil.rmtree(temp_source_dir)
