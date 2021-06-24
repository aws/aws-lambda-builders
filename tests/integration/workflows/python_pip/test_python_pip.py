import os
import shutil
import sys
import tempfile
from unittest import TestCase
import mock

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
import logging

logger = logging.getLogger("aws_lambda_builders.workflows.python_pip.workflow")


class TestPythonPipWorkflow(TestCase):
    """
    Verifies that `python_pip` workflow works by building a Lambda that requires Numpy
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.source_dir = self.TEST_DATA_FOLDER
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.manifest_path_valid = os.path.join(self.TEST_DATA_FOLDER, "requirements-numpy.txt")
        self.manifest_path_invalid = os.path.join(self.TEST_DATA_FOLDER, "requirements-invalid.txt")

        self.test_data_files = {
            "__init__.py",
            "main.py",
            "requirements-invalid.txt",
            "requirements-numpy.txt",
            "local-dependencies",
        }

        self.builder = LambdaBuilder(language="python", dependency_manager="pip", application_framework=None)
        self.runtime = "{language}{major}.{minor}".format(
            language=self.builder.capability.language, major=sys.version_info.major, minor=sys.version_info.minor
        )
        self.runtime_mismatch = {
            "python3.6": "python2.7",
            "python3.7": "python2.7",
            "python2.7": "python3.8",
            "python3.8": "python2.7",
        }

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_must_build_python_project(self):
        self.builder.build(
            self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid, runtime=self.runtime
        )

        if self.runtime == "python2.7":
            expected_files = self.test_data_files.union({"numpy", "numpy-1.15.4.data", "numpy-1.15.4.dist-info"})
        elif self.runtime == "python3.6":
            expected_files = self.test_data_files.union({"numpy", "numpy-1.17.4.dist-info"})
        else:
            expected_files = self.test_data_files.union({"numpy", "numpy-1.20.3.dist-info", "numpy.libs"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_mismatch_runtime_python_project(self):
        # NOTE : Build still works if other versions of python are accessible on the path. eg: /usr/bin/python2.7
        # is still accessible within a python 3 virtualenv.
        try:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_valid,
                runtime=self.runtime_mismatch[self.runtime],
            )
        except WorkflowFailedError as ex:
            self.assertIn("Binary validation failed", str(ex))

    def test_runtime_validate_python_project_fail_open_unsupported_runtime(self):
        with self.assertRaises(WorkflowFailedError):
            self.builder.build(
                self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid, runtime="python2.8"
            )

    def test_must_resolve_local_dependency(self):
        dependency_source_dir = os.path.join(self.source_dir, "local-dependencies", "hello_world")
        dependency_local_manifest = os.path.join(dependency_source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies", "some_package")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(dependency_local_manifest, "w") as f:
            f.write(str(path_to_package))
        self.builder.build(
            dependency_source_dir, self.artifacts_dir, self.scratch_dir, dependency_local_manifest, runtime=self.runtime
        )
        expected_files = {"LocalPackage", "LocalPackage-0.0.0.dist-info", "__init__.py", "requirements.txt"}
        output_files = set(os.listdir(self.artifacts_dir))
        if os.path.exists(dependency_local_manifest):
            os.remove(dependency_local_manifest)
        self.assertEqual(expected_files, output_files)

    def test_must_fail_to_resolve_dependencies(self):

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_invalid, runtime=self.runtime
            )

        # In Python2 a 'u' is now added to the exception string. To account for this, we see if either one is in the
        # output
        message_in_exception = "Invalid requirement: 'adfasf=1.2.3'" in str(
            ctx.exception
        ) or "Invalid requirement: u'adfasf=1.2.3'" in str(ctx.exception)
        self.assertTrue(message_in_exception)

    def test_must_log_warning_if_requirements_not_found(self):
        with mock.patch.object(logger, "warning") as mock_warning:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join("non", "existent", "manifest"),
                runtime=self.runtime,
            )
        expected_files = self.test_data_files
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
        mock_warning.assert_called_once_with(
            "requirements.txt file not found. Continuing the build without dependencies."
        )
