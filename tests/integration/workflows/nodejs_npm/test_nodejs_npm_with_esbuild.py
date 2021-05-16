import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestNodejsNpmWorkflowWithEsbuild(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm", application_framework=None)
        self.runtime = "nodejs14.x"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def testBuildsProjectWithoutDependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
