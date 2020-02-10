import os
import shutil
import sys
import tempfile
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


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

        self.test_data_files = {"__init__.py", "main.py", "requirements-invalid.txt", "requirements-numpy.txt"}

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
        else:
            expected_files = self.test_data_files.union({"numpy", "numpy-1.17.4.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEquals(expected_files, output_files)

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

    def test_must_fail_if_requirements_not_found(self):

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join("non", "existent", "manifest"),
                runtime=self.runtime,
            )

            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join("non", "existent", "manifest"),
                runtime=self.runtime,
            )

        self.assertIn("Requirements file not found", str(ctx.exception))
