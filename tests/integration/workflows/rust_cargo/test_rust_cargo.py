
import os
import shutil
import sys
import tempfile
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestRustCargoWorkflow(TestCase):
    """
    Verifies that `rust_cargo` workflow works by building a basic rust example
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.source_dir = self.TEST_DATA_FOLDER
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.manifest_path_valid = os.path.join(self.TEST_DATA_FOLDER, "Cargo.toml")

        self.builder = LambdaBuilder(language="rust",
                                     dependency_manager="cargo",
                                     application_framework=None)
        self.runtime = "{language}".format(
            language=self.builder.capability.language
        )

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_runs_cargo_build(self):
        output_generated = self.builder.build(self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid,
                           runtime=self.runtime)
        expected_output = os.path.join(self.artifacts_dir, "bootstrap")
        self.assertEquals(expected_output, output_generated)
        self.assertTrue(os.path.isfile(output_generated))
