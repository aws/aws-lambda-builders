import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestGoWorkflow(TestCase):
    """
    Verifies that `go` workflow works by building a Lambda using Go Modules
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="go",
                                     dependency_manager="modules",
                                     application_framework=None)
        self.runtime = "go1.x"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_builds_project_without_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                           os.path.join(source_dir, "go.mod"),
                           runtime=self.runtime,
                           options={"output_executable_name": "no-deps-main"})
        expected_files = {"no-deps-main"}
        output_files = set(os.listdir(self.artifacts_dir))
        print(output_files)
        self.assertEquals(expected_files, output_files)

    def test_builds_project_with_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                           os.path.join(source_dir, "go.mod"),
                           runtime=self.runtime,
                           options={"output_executable_name": "with-deps-main"})
        expected_files = {"with-deps-main"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEquals(expected_files, output_files)

    def test_fails_if_modules_cannot_resolve_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-deps")
        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                               os.path.join(source_dir, "go.mod"),
                               runtime=self.runtime,
                               options={"output_executable_name": "failed"})
        self.assertIn("GoModulesBuilder:Build - Builder Failed: ",
                      str(ctx.exception))
