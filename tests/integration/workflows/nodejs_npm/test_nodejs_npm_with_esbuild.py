import os
import shutil
import tempfile
from unittest import TestCase
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils


class TestNodejsNpmWorkflowWithEsbuild(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm", application_framework=None)
        self.runtime = "nodejs14.x"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    def test_builds_javascript_project_with_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

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

    def test_builds_javascript_project_with_multiple_entrypoints(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-multiple-entrypoints")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
        )

        expected_files = {"included.js", "included.js.map", "included2.js", "included2.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_builds_typescript_projects(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-typescript")

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

    def test_builds_with_external_esbuild(self):
        osutils = OSUtils()
        npm = SubprocessNpm(osutils)
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")
        esbuild_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-binary")

        npm.run(["ci"], cwd=esbuild_dir)

        binpath = npm.run(["bin"], cwd=esbuild_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            executable_search_paths=[binpath],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_with_download_dependencies_and_dependencies_dir(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
        )

        expected_files = {"included.js.map", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = {"included.js.map", "included.js"}
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertEqual(expected_modules, output_modules)
