import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.utils import permissions


class TestNodejsNpmWorkflow(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps")

        self.builder = LambdaBuilder(language="nodejs",
                                     dependency_manager="npm",
                                     application_framework=None)
        self.runtime = "nodejs8.10"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_builds_project_without_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        with permissions(directory=source_dir, entry_mode=0o555, exit_mode=0o755):

            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                               os.path.join(source_dir, "package.json"),
                               runtime=self.runtime)

            expected_files = {"package.json", "included.js"}
            output_files = set(os.listdir(self.artifacts_dir))
            self.assertEquals(expected_files, output_files)

    def test_builds_project_with_remote_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        with permissions(directory=source_dir, entry_mode=0o555, exit_mode=0o755):
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                               os.path.join(source_dir, "package.json"),
                               runtime=self.runtime)

            expected_files = {"package.json", "included.js", "node_modules"}
            output_files = set(os.listdir(self.artifacts_dir))
            self.assertEquals(expected_files, output_files)

            expected_modules = {"minimal-request-promise"}
            output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
            self.assertEquals(expected_modules, output_modules)

    def test_builds_project_with_npmrc(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npmrc")

        with permissions(directory=source_dir, entry_mode=0o555, exit_mode=0o755):

            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                               os.path.join(source_dir, "package.json"),
                               runtime=self.runtime)

            expected_files = {"package.json", "included.js", "node_modules"}
            output_files = set(os.listdir(self.artifacts_dir))

            self.assertEquals(expected_files, output_files)

            expected_modules = {"fake-http-request"}
            output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
            self.assertEquals(expected_modules, output_modules)

    def test_fails_if_npm_cannot_resolve_dependencies(self):

        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-deps")

        with permissions(directory=source_dir, entry_mode=0o555, exit_mode=0o755):

            with self.assertRaises(WorkflowFailedError) as ctx:
                self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                                   os.path.join(source_dir, "package.json"),
                                   runtime=self.runtime)

            self.assertIn("No matching version found "
                          "for minimal-request-promise@0.0.0-NON_EXISTENT", str(ctx.exception))

    def test_fails_if_package_json_is_broken(self):

        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-package")

        with permissions(directory=source_dir, entry_mode=0o555, exit_mode=0o755):

            with self.assertRaises(WorkflowFailedError) as ctx:
                self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                                   os.path.join(source_dir, "package.json"),
                                   runtime=self.runtime)

            self.assertIn("Unexpected end of JSON input", str(ctx.exception))
