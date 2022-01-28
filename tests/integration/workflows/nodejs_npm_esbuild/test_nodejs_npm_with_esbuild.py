import os
import shutil
import tempfile
from unittest import TestCase
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildExecutionError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.utils import EXPERIMENTAL_FLAG_ESBUILD


class TestNodejsNpmWorkflowWithEsbuild(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm", application_framework="esbuild")
        self.runtime = "nodejs14.x"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_doesnt_build_without_feature_flag(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        with self.assertRaises(EsbuildExecutionError) as context:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=self.runtime,
            )
        self.assertEqual(str(context.exception), "Esbuild Failed: Feature flag must be enabled to use this workflow")

    def test_builds_javascript_project_with_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
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
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
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
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
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
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_fails_if_package_json_is_broken(self):

        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-package")

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=self.runtime,
                experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            )

        self.assertIn("NodejsNpmEsbuildBuilder:ParseManifest", str(ctx.exception))
