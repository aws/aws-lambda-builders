import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestRustCargo(TestCase):
    """
    Verifies that rust workflow works by building a Lambda using cargo
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.runtime = "provided"
        # this inherently tests that rust was was wired up though
        # the registry, a runtime error would be raised here if not
        self.builder = LambdaBuilder(language="rust", dependency_manager="cargo", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_builds_hello_project(self):
        pass
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "hello")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "hello"},
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEquals(expected_files, output_files)
