
import os
import shutil
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

        self.test_data_files = set(os.listdir(self.TEST_DATA_FOLDER))

        self.builder = LambdaBuilder(language="python",
                                     dependency_manager="pip",
                                     application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_must_build_python_project(self):
        self.builder.build(self.source_dir, self.artifacts_dir, None, self.manifest_path_valid,
                           runtime="python2.7")

        expected_files = self.test_data_files.union({"numpy", "numpy-1.15.4.data", "numpy-1.15.4.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEquals(expected_files, output_files)

    def test_runtime_validate_python_project(self):
        with self.assertRaises(ValueError):
            self.builder.build(self.source_dir, self.artifacts_dir, None, self.manifest_path_valid,
                               runtime="python2.8")

    def test_must_fail_to_resolve_dependencies(self):

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(self.source_dir, self.artifacts_dir, None, self.manifest_path_invalid,
                               runtime="python2.7")

        self.assertIn("Invalid requirement: 'adfasf=1.2.3'", str(ctx.exception))

    def test_must_fail_if_requirements_not_found(self):

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(self.source_dir, self.artifacts_dir, None, os.path.join("non", "existent", "manifest"),
                               runtime="python2.7")

        self.assertIn("Requirements file not found", str(ctx.exception))
