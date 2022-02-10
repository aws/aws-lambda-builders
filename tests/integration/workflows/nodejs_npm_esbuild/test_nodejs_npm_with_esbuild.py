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

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm-esbuild", application_framework=None)
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

        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_builds_javascript_project_with_multiple_entrypoints(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-multiple-entrypoints")

        options = {"entry_points": ["included.js", "included2.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map", "included2.js", "included2.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_builds_typescript_projects(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-typescript")

        options = {"entry_points": ["included.ts"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            options=options,
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

        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            options=options,
            executable_search_paths=[binpath],
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_no_options_passed_to_esbuild(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        with self.assertRaises(WorkflowFailedError) as context:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=self.runtime,
                experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            )

        self.assertEqual(str(context.exception), "NodejsNpmEsbuildBuilder:EsbuildBundle - entry_points not set ({})")

    def test_bundle_with_implicit_file_types(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "implicit-file-types")

        options = {"entry_points": ["included", "implicit"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js.map", "implicit.js.map", "implicit.js", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_bundles_project_without_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-package-esbuild")
        options = {"entry_points": ["included"]}

        osutils = OSUtils()
        npm = SubprocessNpm(osutils)
        esbuild_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-binary")
        npm.run(["ci"], cwd=esbuild_dir)
        binpath = npm.run(["bin"], cwd=esbuild_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=self.runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            executable_search_paths=[binpath],
        )

        expected_files = {"included.js.map", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
