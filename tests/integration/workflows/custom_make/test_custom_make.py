import os
import shutil
import tempfile
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestCustomMakeWorkflow(TestCase):
    """
    Verifies that `custom_make` workflow works by building a Lambda that requires Numpy
    """

    MAKEFILE_DIRECTORY = "makefile-root"
    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata", MAKEFILE_DIRECTORY)

    def setUp(self):
        self.source_dir = self.TEST_DATA_FOLDER
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.manifest_path_valid = os.path.join(self.TEST_DATA_FOLDER, "Makefile")

        self.test_data_files = {"__init__.py", "main.py", "requirements-requests.txt"}

        self.builder = LambdaBuilder(language="provided", dependency_manager=None, application_framework=None)
        self.runtime = "provided"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_must_build_python_project_through_makefile(self):
        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_valid,
            runtime=self.runtime,
            options={"build_logical_id": "HelloWorldFunction"},
        )
        dependencies_installed = {
            "chardet",
            "urllib3",
            "idna",
            "urllib3-1.25.11.dist-info",
            "chardet-3.0.4.dist-info",
            "certifi-2020.6.20.dist-info",
            "certifi",
            "idna-2.10.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
        }

        expected_files = self.test_data_files.union(dependencies_installed)
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_build_python_project_failed_through_makefile_no_python_source_in_default_working_directory(self):
        source_code = os.path.join(os.path.dirname(__file__), "testdata", "makefile-in-different-working-directory")
        manifest_path_valid = os.path.join(source_code, "Makefile")
        with self.assertRaises(WorkflowFailedError):
            self.builder.build(
                source_code,
                self.artifacts_dir,
                self.scratch_dir,
                manifest_path_valid,
                runtime=self.runtime,
                options={"build_logical_id": "HelloWorldFunction"},
            )

    def test_must_build_python_project_through_makefile_with_custom_working_directory(self):
        source_code = os.path.join(os.path.dirname(__file__), "testdata", "makefile-in-different-working-directory")
        manifest_path_valid = os.path.join(source_code, "Makefile")
        working_directory = os.path.join(source_code, "source_code")
        self.builder.build(
            source_code,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path_valid,
            runtime=self.runtime,
            options={"build_logical_id": "HelloWorldFunction", "working_directory": working_directory},
        )
        dependencies_installed = {
            "chardet",
            "urllib3",
            "idna",
            "urllib3-1.25.11.dist-info",
            "chardet-3.0.4.dist-info",
            "certifi-2020.4.5.2.dist-info",
            "certifi",
            "idna-2.10.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
        }

        expected_files = self.test_data_files.union(dependencies_installed)
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_must_build_python_project_through_makefile_unknown_target(self):
        with self.assertRaises(WorkflowFailedError):
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_valid,
                runtime=self.runtime,
                options={"build_logical_id": "HelloWorldFunction2"},
            )

    def test_must_build_python_project_through_makefile_in_source(self):
        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_valid,
            runtime=self.runtime,
            options={"build_logical_id": "HelloWorldFunction"},
            build_in_source=True,
        )
        dependencies_installed = {
            "chardet",
            "urllib3",
            "idna",
            "urllib3-1.25.11.dist-info",
            "chardet-3.0.4.dist-info",
            "certifi-2020.4.5.2.dist-info",
            "certifi",
            "idna-2.10.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
        }

        expected_files = self.test_data_files.union(dependencies_installed)
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
