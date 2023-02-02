import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildExecutionError
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
        self.osutils = OSUtils()
        self._set_esbuild_binary_path()

    def _set_esbuild_binary_path(self):
        npm = SubprocessNpm(self.osutils)
        esbuild_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-binary")
        npm.run(["install"], cwd=esbuild_dir)
        self.root_path = npm.run(["root"], cwd=esbuild_dir)
        self.binpath = Path(self.root_path, ".bin")

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_javascript_project_with_dependencies_with_resource_wildcard(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-with-resources")

        options = {"entry_points": ["included.js"], "include": "resources/file*"}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files1 = {"included.js", "resources"}
        output_files1 = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files1, output_files1)

        expected_files2 = {"file1.txt", "file2.txt"}
        output_files2 = set(os.listdir(os.path.join(self.artifacts_dir, "resources")))
        self.assertEqual(expected_files2, output_files2)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_javascript_project_with_dependencies_with_resource_list(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-with-resources")

        options = {"entry_points": ["included.js"], "include": ["resources/file1.txt", "resources/file2.txt"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files1 = {"included.js", "resources"}
        output_files1 = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files1, output_files1)

        expected_files2 = {"file1.txt", "file2.txt"}
        output_files2 = set(os.listdir(os.path.join(self.artifacts_dir, "resources")))
        self.assertEqual(expected_files2, output_files2)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_javascript_project_with_no_dependencies_and_resource_list(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild-with-resources")

        options = {"entry_points": ["included.js"], "include": ["resources/file1.txt", "resources/file2.txt"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files1 = {"included.js", "resources"}
        output_files1 = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files1, output_files1)

        expected_files2 = {"file1.txt", "file2.txt"}
        output_files2 = set(os.listdir(os.path.join(self.artifacts_dir, "resources")))
        self.assertEqual(expected_files2, output_files2)

    # @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_error_javascript_project_with_no_dependencies_and_invalid_resource(self, runtime="nodejs18.x"):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild-with-resources")
        options = {"entry_points": ["included.js"], "include": {}}

        self.assertRaisesRegex(
            ValueError,
            "Resource include items must be strings or lists of strings",
            self.builder.build,
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js", "included2.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_with_external_esbuild(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")
        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_no_options_passed_to_esbuild(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        with self.assertRaises(WorkflowFailedError) as context:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
                experimental_flags=[],
                executable_search_paths=[self.binpath],
            )

        self.assertEqual(str(context.exception), "NodejsNpmEsbuildBuilder:EsbuildBundle - entry_points not set ({})")

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"implicit.js", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_bundles_project_without_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-package-esbuild")
        options = {"entry_points": ["included"]}

        osutils = OSUtils()
        npm = SubprocessNpm(osutils)
        esbuild_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-binary")
        npm.run(["install"], cwd=esbuild_dir)
        binpath = Path(npm.run(["root"], cwd=esbuild_dir), ".bin")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_with_remote_dependencies_without_download_dependencies_with_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-no-node_modules")
        options = {"entry_points": ["included.js"]}

        osutils = OSUtils()
        npm = SubprocessNpm(osutils)
        esbuild_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-binary")
        npm.run(["install"], cwd=esbuild_dir)
        binpath = Path(npm.run(["root"], cwd=esbuild_dir), ".bin")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            options=options,
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
            experimental_flags=[],
            executable_search_paths=[binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
                experimental_flags=[],
                executable_search_paths=[self.binpath],
            )

        self.assertEqual(
            str(context.exception),
            "Esbuild Failed: Lambda Builders was unable to find the location of the dependencies since a "
            "dependencies directory was not provided and downloading dependencies is disabled.",
        )

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
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
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_javascript_project_with_external(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild-externals")

        options = {"entry_points": ["included.js"], "external": ["minimal-request-promise"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
        with open(str(os.path.join(self.artifacts_dir, "included.js"))) as f:
            js_file = f.read()
            # Check that the module has been require() instead of bundled
            self.assertIn('require("minimal-request-promise")', js_file)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_javascript_project_with_loader(self, runtime):
        osutils = OSUtils()
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild-loader")

        options = {"entry_points": ["included.js"], "loader": [".reference=json"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        included_js_path = os.path.join(self.artifacts_dir, "included.js")

        # check that the .reference file is correctly bundled as code by running the result
        self.assertEqual(
            osutils.check_output(included_js_path),
            str.encode(
                "===\n"
                "The Muses\n"
                "===\n"
                "\n"
                "\tcalliope: eloquence and heroic poetry\n"
                "\terato: lyric or erotic poetry\n"
                "\tmelpomene: tragedy\n"
                "\tpolymnia: sacred poetry\n"
                "\tterpsichore: dance\n"
                "\tthalia: comedy\n"
                "\turania: astronomy and astrology"
            ),
        )

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_includes_sourcemap_if_requested(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        options = {"entry_points": ["included.js"], "sourcemap": True}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js", "included.js.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_esbuild_produces_mjs_output_files(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")
        options = {"entry_points": ["included.js"], "sourcemap": True, "out_extension": [".js=.mjs"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.mjs", "included.mjs.map"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
