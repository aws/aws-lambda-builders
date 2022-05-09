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
from parameterized import parameterized


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

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm-esbuild", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_doesnt_build_without_feature_flag(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        with self.assertRaises(EsbuildExecutionError) as context:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
            )
        self.assertEqual(str(context.exception), "Esbuild Failed: Feature flag must be enabled to use this workflow")

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_javascript_project_with_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_javascript_project_with_multiple_entrypoints(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-multiple-entrypoints")

        options = {"entry_points": ["included.js", "included2.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map", "included2.js", "included2.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_typescript_projects(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-typescript")

        options = {"entry_points": ["included.ts"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_with_external_esbuild(self, runtime):
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
            runtime=runtime,
            options=options,
            executable_search_paths=[binpath],
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_no_options_passed_to_esbuild(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        with self.assertRaises(WorkflowFailedError) as context:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
                experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            )

        self.assertEqual(str(context.exception), "NodejsNpmEsbuildBuilder:EsbuildBundle - entry_points not set ({})")

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_bundle_with_implicit_file_types(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "implicit-file-types")

        options = {"entry_points": ["included", "implicit"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js.map", "implicit.js.map", "implicit.js", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_bundles_project_without_dependencies(self, runtime):
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
            runtime=runtime,
            options=options,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            executable_search_paths=[binpath],
        )

        expected_files = {"included.js.map", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_project_with_remote_dependencies_without_download_dependencies_with_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-no-node_modules")
        options = {"entry_points": ["included.js"]}

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
            options=options,
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            executable_search_paths=[binpath],
        )

        expected_files = {"included.js.map", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_project_with_remote_dependencies_with_download_dependencies_and_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-no-node_modules")
        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js.map", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_project_with_remote_dependencies_without_download_dependencies_without_dependencies_dir(
        self, runtime
    ):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-no-node_modules")

        with self.assertRaises(EsbuildExecutionError) as context:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
                dependencies_dir=None,
                download_dependencies=False,
                experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
            )

        self.assertEqual(str(context.exception), "Esbuild Failed: Lambda Builders encountered and invalid workflow")

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",)])
    def test_builds_project_without_combine_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-no-node_modules")
        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
            combine_dependencies=False,
            experimental_flags=[EXPERIMENTAL_FLAG_ESBUILD],
        )

        expected_files = {"included.js.map", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)
