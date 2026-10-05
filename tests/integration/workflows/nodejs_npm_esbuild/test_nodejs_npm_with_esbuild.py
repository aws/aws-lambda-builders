import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.supported_runtimes import NODEJS_RUNTIMES
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildExecutionError
from parameterized import parameterized


class TestNodejsNpmWorkflowWithEsbuild(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")
    SUPPORTED_RUNTIMES = [(runtime,) for runtime in NODEJS_RUNTIMES]

    def setUp(self):
        self.source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()
        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps-esbuild")
        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm-esbuild", application_framework=None)
        self.osutils = OSUtils()
        self._set_esbuild_binary_path()

        # use this so tests don't modify actual testdata, and we can parallelize
        self.temp_dir = tempfile.mkdtemp()
        self.temp_testdata_dir = os.path.join(self.temp_dir, "testdata")
        shutil.copytree(self.TEST_DATA_FOLDER, self.temp_testdata_dir)

    def _set_esbuild_binary_path(self):
        npm = SubprocessNpm(self.osutils)
        esbuild_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-binary")
        npm.run(["install"], cwd=esbuild_dir)
        self.root_path = npm.run(["root"], cwd=esbuild_dir)
        self.binpath = Path(self.root_path, ".bin")

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.temp_dir)

        # clean up dependencies that were installed in source dir
        source_dependencies = os.path.join(self.source_dir, "node_modules")
        if os.path.exists(source_dependencies):
            shutil.rmtree(source_dependencies)

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
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

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_esbuild_produces_sourcemap_without_source_contents(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")
        options = {"entry_points": ["included.js"], "sourcemap": True, "sources_content": "false"}

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
        with open(Path(self.artifacts_dir, "included.js.map")) as f:
            sourcemap = json.load(f)
        self.assertNotIn("sourcesContent", sourcemap)
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_esbuild_can_build_in_source(self, runtime):
        options = {"entry_points": ["included.js"]}

        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(self.source_dir, "package.json"),
            runtime=runtime,
            options=options,
            executable_search_paths=[self.binpath],
            build_in_source=True,
        )

        # dependencies installed in source folder
        self.assertIn("node_modules", os.listdir(self.source_dir))

        # dependencies not in scratch
        self.assertNotIn("node_modules", os.listdir(self.scratch_dir))

        # bundle is in artifacts
        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_esbuild_can_build_in_source_with_local_dependency(self, runtime):
        self.source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-local-dependency")

        options = {"entry_points": ["included.js"]}

        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(self.source_dir, "package.json"),
            runtime=runtime,
            options=options,
            executable_search_paths=[self.binpath],
            build_in_source=True,
        )

        # dependencies installed in source folder
        self.assertIn("node_modules", os.listdir(self.source_dir))

        # dependencies not in scratch
        self.assertNotIn("node_modules", os.listdir(self.scratch_dir))

        # bundle is in artifacts
        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_esbuild_can_build_in_source_in_workspaces_monorepo_with_locked_versions(self, runtime):
        # npm workspaces keep one lockfile at the monorepo root rather than next to each function. This one pins
        # minimal-request-promise to 1.3.0 while the function's manifest allows ^1.3.0, so a build that ignored
        # the lockfile would silently upgrade the dependency in the developer's own source tree.
        monorepo_dir = os.path.join(self.temp_testdata_dir, "workspaces-monorepo")
        source_dir = os.path.join(monorepo_dir, "packages", "fn")
        lockfile_path = os.path.join(monorepo_dir, "package-lock.json")
        with open(lockfile_path, "rb") as lockfile:
            original_lockfile = lockfile.read()

        options = {"entry_points": ["included.js"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            options=options,
            executable_search_paths=[self.binpath],
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        # the locked version is what got installed, and npm hoists it to the monorepo root
        installed_manifest = os.path.join(monorepo_dir, "node_modules", "minimal-request-promise", "package.json")
        self.assertTrue(os.path.isfile(installed_manifest))
        with open(installed_manifest) as manifest:
            self.assertEqual(json.load(manifest)["version"], "1.3.0")

        # the root lockfile records the workspace package as a link entry, which is the tree --install-links
        # overrides for a file: dependency. npm exempts workspaces from that, so the link still resolves to
        # the developer's own packages/fn rather than a packed snapshot of it. Compare resolved paths rather
        # than calling os.path.islink: npm links a workspace with a junction on Windows, which is a directory
        # to Python, not a link.
        workspace_link = os.path.join(monorepo_dir, "node_modules", "@workspaces-monorepo", "fn")
        self.assertEqual(os.path.realpath(workspace_link), os.path.realpath(source_dir))

        # the install runs inside the workspace package but reifies the root, so the root lockfile is the
        # developer file most at risk - it has to come back untouched. This fixture is lockfileVersion 2,
        # which npm migrates in memory before reifying; npm-deps-with-lockfile covers version 3.
        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

        # bundle is in artifacts, and it resolved the hoisted dependency: requiring it would raise
        # MODULE_NOT_FOUND if esbuild had left the import unbundled
        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        bundle = os.path.join(self.artifacts_dir, "included.js")
        require_bundle = subprocess.run(
            ["node", "-e", "require(process.argv[1])", bundle], capture_output=True, text=True
        )
        self.assertEqual(require_bundle.returncode, 0, require_bundle.stderr)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_javascript_project_ignoring_relevant_flags(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps-esbuild")

        options = {"entry_points": ["included.js"], "use_npm_ci": True}

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

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_typescript_projects_with_external_manifest(self, runtime):
        base_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")

        options = {"entry_points": ["included.ts"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_typescript_projects_with_external_manifest_with_dependencies_dir_without_combine(self, runtime):
        base_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")

        options = {"entry_points": ["included.ts"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
            combine_dependencies=False,
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_typescript_projects_with_external_manifest_with_dependencies_dir_with_combine(self, runtime):
        base_dir = os.path.join(self.TEST_DATA_FOLDER, "esbuild-manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")

        options = {"entry_points": ["included.ts"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
            combine_dependencies=True,
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_typescript_projects_with_external_manifest_and_local_depends(self, runtime):
        base_dir = os.path.join(self.temp_testdata_dir, "esbuild-manifest-outside-root-with-local-depends")
        source_dir = os.path.join(base_dir, "src")

        options = {"entry_points": ["included.ts"]}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            options=options,
            experimental_flags=[],
            executable_search_paths=[self.binpath],
            build_in_source=True,
        )

        expected_files = {"included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # dependencies installed in source folder
        self.assertIn("node_modules", os.listdir(source_dir))
        self.assertIn("node_modules", os.listdir(os.path.join(base_dir, "manifest")))

        expected_modules = ["minimal-request-promise", "axios"]
        output_modules = set(os.listdir(os.path.join(source_dir, "node_modules")))
        self.assertTrue(all(expected_module in output_modules for expected_module in expected_modules))

        output_modules = set(os.listdir(os.path.join(os.path.join(base_dir, "manifest"), "node_modules")))
        self.assertTrue(all(expected_module in output_modules for expected_module in expected_modules))

        # dependencies not in scratch
        self.assertNotIn("node_modules", os.listdir(self.scratch_dir))
