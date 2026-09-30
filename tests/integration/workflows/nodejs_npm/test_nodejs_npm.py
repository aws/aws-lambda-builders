import itertools
import json
import logging
import os
import shutil
import subprocess
import tempfile

from unittest import TestCase, mock

from parameterized import parameterized

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import SharedDependenciesInstallError, WorkflowFailedError
from aws_lambda_builders.supported_runtimes import NODEJS_RUNTIMES
from aws_lambda_builders.workflows.nodejs_npm.lockfile_closure import production_closure
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import EXPERIMENTAL_FLAG_NODEJS_MONOREPO, OSUtils
from tests.testing_utils import read_link_without_junction_prefix

logger = logging.getLogger("aws_lambda_builders.workflows.nodejs_npm.workflow")


class TestNodejsNpmWorkflow(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    # Use centralized Node.js runtimes
    SUPPORTED_RUNTIMES = [(runtime,) for runtime in NODEJS_RUNTIMES]

    # Generate combinations of runtimes and lockfile types
    LOCKFILE_TYPES = ["package-lock", "shrinkwrap", "package-lock-and-shrinkwrap"]
    RUNTIME_LOCKFILE_COMBINATIONS = list(itertools.product(NODEJS_RUNTIMES, LOCKFILE_TYPES))

    # both in-source install paths: the flag selects `npm install --omit=dev`, its absence `npm update
    # --omit=dev --no-package-lock`, and dev-dependency pruning is asserted on each
    DEV_DEPENDENCY_CASES = [
        (f"{runtime}_{'with_flag' if flags else 'without_flag'}", runtime, flags)
        for runtime in NODEJS_RUNTIMES
        for flags in ([EXPERIMENTAL_FLAG_NODEJS_MONOREPO], [])
    ]

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()

        # use this so tests don't modify actual testdata, and we can parallelize
        self.temp_dir = tempfile.mkdtemp()
        self.temp_testdata_dir = os.path.join(self.temp_dir, "testdata")
        shutil.copytree(self.TEST_DATA_FOLDER, self.temp_testdata_dir)

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps")

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)
        shutil.rmtree(self.temp_dir)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_without_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_without_manifest(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-manifest")

        with mock.patch.object(logger, "warning") as mock_warning:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
            )

        expected_files = {"app.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        mock_warning.assert_called_once_with("package.json file not found. Continuing the build without dependencies.")
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_and_excludes_hidden_aws_sam(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "excluded-files")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_remote_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_npmrc(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npmrc")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

        expected_modules = {"fake-http-request"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

    @parameterized.expand(RUNTIME_LOCKFILE_COMBINATIONS)
    def test_builds_project_with_lockfile(self, runtime, dir_name):
        expected_files_common = {"package.json", "included.js", "node_modules"}
        expected_files_by_dir_name = {
            "package-lock": {"package-lock.json"},
            "shrinkwrap": {"npm-shrinkwrap.json"},
            "package-lock-and-shrinkwrap": {"package-lock.json", "npm-shrinkwrap.json"},
        }

        source_dir = os.path.join(self.TEST_DATA_FOLDER, dir_name)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = expected_files_common.union(expected_files_by_dir_name[dir_name])

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_fails_if_npm_cannot_resolve_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-deps")

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
            )

        self.assertIn("No matching version found for aws-sdk@2.997.999", str(ctx.exception))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_remote_dependencies_without_download_dependencies_with_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_remote_dependencies_with_download_dependencies_and_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
        )

        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_remote_dependencies_without_download_dependencies_without_dependencies_dir(
        self, runtime
    ):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        with mock.patch.object(logger, "info") as mock_info:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
                dependencies_dir=None,
                download_dependencies=False,
            )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_without_combine_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
            combine_dependencies=False,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_download_dependencies(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_removed_dependencies_and_a_lockfile(self, runtime):
        # a project with a lockfile installs the locked versions, and still drops a dependency that was
        # removed from the manifest even though the lockfile it reads still lists it
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps-with-lockfile")
        lockfile_path = os.path.join(source_dir, "package-lock.json")
        with open(lockfile_path, "rb") as lockfile:
            original_lockfile = lockfile.read()

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertIn("minimal-request-promise", set(os.listdir(source_node_modules)))
        installed_manifest = os.path.join(source_node_modules, "minimal-request-promise", "package.json")
        with open(installed_manifest) as manifest:
            # the lockfile pins 1.3.0 while the manifest allows ^1.3.0
            self.assertEqual(json.load(manifest)["version"], "1.3.0")

        # `--omit=dev` keeps the `ms` devDependency out of node_modules while the lockfile keeps its entry
        self.assertNotIn("ms", set(os.listdir(source_node_modules)))

        # the install runs in the developer's own directory, so it must leave their lockfile untouched,
        # `ms` entry included
        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

        shutil.copy2(
            os.path.join(self.temp_testdata_dir, "no-deps", "package.json"),
            os.path.join(source_dir, "package.json"),
        )

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        self.assertNotIn("minimal-request-promise", set(os.listdir(source_node_modules)))
        # still untouched with the lockfile now out of date: the manifest no longer lists the dependency
        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_a_version_1_lockfile(self, runtime):
        # npm 6 wrote lockfileVersion 1 and npm 7+ has to migrate it in memory before it can reify, which
        # is a different write path from reifying a version 2 or 3 lockfile directly. The locked versions
        # still have to win, and the developer's file still has to come back untouched - in its original
        # format, not migrated in place.
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps-with-v1-lockfile")
        lockfile_path = os.path.join(source_dir, "package-lock.json")
        with open(lockfile_path, "rb") as lockfile:
            original_lockfile = lockfile.read()

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        source_node_modules = os.path.join(source_dir, "node_modules")
        installed_manifest = os.path.join(source_node_modules, "minimal-request-promise", "package.json")
        with open(installed_manifest) as manifest:
            # the lockfile pins 1.3.0 while the manifest allows ^1.3.0, so this version can only come
            # from npm having read the version 1 lockfile
            self.assertEqual(json.load(manifest)["version"], "1.3.0")

        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

    @parameterized.expand(DEV_DEPENDENCY_CASES)
    def test_build_in_source_drops_already_installed_dev_dependencies(self, _name, runtime, experimental_flags):
        # building in source installs into the developer's own directory, which normally already holds the
        # dev dependencies their own `npm install` put there. Those must not reach the artifacts, which for
        # this workflow are a symlink to the same node_modules.
        #
        # Run on BOTH install paths. The flag decides which npm command resolves the tree - `npm install
        # --omit=dev --install-links` with it, `npm update --omit=dev --no-package-lock` without - and the
        # pruning has to hold either way. Parameterised rather than flagged on, because a single opted-in
        # case would stop covering the path this PR leaves alone, and a single opted-out case would leave
        # the new command's pruning unverified.
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps-with-lockfile")
        source_node_modules = os.path.join(source_dir, "node_modules")

        # the developer's own install: the `ms` devDependency is present before the build. Go through
        # SubprocessNpm rather than a bare `npm`, since the executable is `npm.cmd` on Windows.
        SubprocessNpm(OSUtils()).run(["install", "--silent", "--no-audit", "--no-fund"], cwd=source_dir)
        self.assertIn("ms", set(os.listdir(source_node_modules)))

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            experimental_flags=experimental_flags,
        )

        installed = set(os.listdir(source_node_modules))
        self.assertNotIn("ms", installed)
        self.assertIn("minimal-request-promise", installed)
        # the artifacts link resolves to that same directory, so name what it must contain rather than
        # comparing it with itself - a set-equality check against `installed` holds however the build behaved
        artifacts_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertIn("minimal-request-promise", artifacts_modules)
        self.assertNotIn("ms", artifacts_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_a_local_dependency_and_a_lockfile(self, runtime):
        # a lockfile written by a plain `npm install` records a file: dependency as a link entry
        # ("resolved": "../npm-deps", "link": true), which is the tree --install-links exists to override.
        # Reading a lockfile and passing --install-links used to be mutually exclusive here, because every
        # build-in-source install ran with --no-package-lock, so this combination needs pinning: the local
        # dependency has to land as a real directory, or the artifacts ship a symlink pointing outside them.
        source_dir = os.path.join(self.temp_testdata_dir, "with-local-dependency-and-lockfile")
        lockfile_path = os.path.join(source_dir, "package-lock.json")
        with open(lockfile_path, "rb") as lockfile:
            original_lockfile = lockfile.read()

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        source_node_modules = os.path.join(source_dir, "node_modules")
        local_dependency = os.path.join(source_node_modules, "local-dependency")
        # --install-links wins over the lockfile's link entry: a real directory holding the package's files
        self.assertFalse(os.path.islink(local_dependency))
        self.assertTrue(os.path.isdir(local_dependency))
        self.assertTrue(os.path.isfile(os.path.join(local_dependency, "included.js")))

        installed_manifest = os.path.join(source_node_modules, "minimal-request-promise", "package.json")
        with open(installed_manifest) as manifest:
            # the lockfile pins 1.3.0 while the manifest allows ^1.3.0, so the lockfile was read even
            # though --install-links was also in effect
            self.assertEqual(json.load(manifest)["version"], "1.3.0")

        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_in_workspaces_monorepo_links_the_hoisted_dependencies(self, runtime):
        # npm hoists a workspace package's dependencies to the monorepo root, so node_modules never
        # appears beside the function. This workflow ships node_modules rather than bundling it, so the
        # artifacts have to reach the directory npm actually used.
        monorepo_dir = os.path.join(self.temp_testdata_dir, "workspaces-monorepo")
        source_dir = os.path.join(monorepo_dir, "endpoints", "fn")

        # the developer's own install, at the monorepo root, which is how a workspaces project is set up
        # before `sam build` ever runs. It installs every endpoint's dependencies into one node_modules.
        SubprocessNpm(OSUtils()).run(["install", "--silent", "--no-audit", "--no-fund"], cwd=monorepo_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        # npm hoisted to the monorepo root and left nothing beside the function
        self.assertFalse(os.path.exists(os.path.join(source_dir, "node_modules")))

        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.exists(artifacts_node_modules), "the artifacts have no node_modules at all")

        installed = set(os.listdir(artifacts_node_modules))
        self.assertIn("minimal-request-promise", installed)
        self.assertIn("@nodejs-workspaces-monorepo", installed)

        # npm hoists every workspace package's dependencies into the one node_modules it creates, so the
        # sibling endpoint's `ms` is sitting right beside this function's own dependencies. It must not
        # reach this function's artifacts.
        self.assertIn("ms", set(os.listdir(os.path.join(monorepo_dir, "node_modules"))))
        self.assertNotIn("ms", installed)

        # the workspace package this function depends on is reachable under its own name, which is not the
        # name of the directory it lives in
        self.assertTrue(
            os.path.exists(os.path.join(artifacts_node_modules, "@nodejs-workspaces-monorepo", "shared", "index.js"))
        )

        # the locked version won, not the newest one the range allows
        installed_manifest = os.path.join(artifacts_node_modules, "minimal-request-promise", "package.json")
        with open(installed_manifest) as manifest:
            self.assertEqual(json.load(manifest)["version"], "1.3.0")

        # the handler's own requires resolve from the artifacts directory - the property that makes this
        # a deployable package rather than a directory that merely holds the right names
        require_handler = subprocess.run(
            ["node", "-e", "require('./included.js')"],
            cwd=self.artifacts_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(require_handler.returncode, 0, require_handler.stderr)

    def test_the_lockfile_closure_agrees_with_npm_ls_on_a_real_install(self):
        # the property that lets the lockfile replace `npm ls`, and one a unit test cannot establish:
        # it would compare this code against a fixture written from this code
        monorepo_dir = os.path.join(self.temp_testdata_dir, "workspaces-monorepo")
        npm = SubprocessNpm(OSUtils())
        npm.run(["install", "--silent", "--no-audit", "--no-fund"], cwd=monorepo_dir)

        for endpoint in ("fn", "other"):
            install_dir = os.path.join(monorepo_dir, "endpoints", endpoint)
            from_npm = npm.resolve_dependency_closure(install_dir)
            self.assertIsNotNone(from_npm, "npm ls must answer, or this test proves nothing")
            from_lockfile = production_closure(monorepo_dir, install_dir)
            self.assertIsNotNone(from_lockfile, "npm's hidden lockfile must be readable by the resolver")

            normalise = {os.path.normcase(os.path.realpath(p)) for p in from_npm}
            self.assertEqual(
                {os.path.normcase(os.path.realpath(p)) for p in from_lockfile},
                normalise,
                f"the two closure sources disagree for endpoints/{endpoint}",
            )

    def test_a_manifest_the_project_lockfile_has_not_recorded_still_reaches_the_artifacts(self):
        # `npm install --no-save` installs a newly declared dependency without writing
        # package-lock.json, so a closure read from that file would drop it
        monorepo_dir = os.path.join(self.temp_testdata_dir, "workspaces-monorepo")
        source_dir = os.path.join(monorepo_dir, "endpoints", "fn")
        npm = SubprocessNpm(OSUtils())
        npm.run(["install", "--silent", "--no-audit", "--no-fund"], cwd=monorepo_dir)

        # declare a dependency the lockfile knows nothing about, exactly as editing package.json does
        manifest_path = os.path.join(source_dir, "package.json")
        with open(manifest_path) as manifest:
            manifest_json = json.load(manifest)
        manifest_json["dependencies"]["ms"] = "^2.1.3"
        with open(manifest_path, "w") as manifest:
            json.dump(manifest_json, manifest)
        with open(os.path.join(monorepo_dir, "package-lock.json")) as lockfile:
            self.assertNotIn("ms", json.load(lockfile)["packages"]["endpoints/fn"].get("dependencies", {}))

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            # one runtime: this pins the closure source, which no runtime varies
            runtime=NODEJS_RUNTIMES[-1],
            build_in_source=True,
            experimental_flags=[EXPERIMENTAL_FLAG_NODEJS_MONOREPO],
        )

        self.assertIn("ms", set(os.listdir(os.path.join(self.artifacts_dir, "node_modules"))))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_removed_dependencies(self, runtime):
        # run a build with default requirements and confirm dependencies are downloaded
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # update package.json with empty one and re-run the build then confirm node_modules are cleared up
        shutil.copy2(
            os.path.join(self.temp_testdata_dir, "no-deps", "package.json"),
            os.path.join(self.temp_testdata_dir, "npm-deps", "package.json"),
        )

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
        )
        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        self.assertIn(".package-lock.json", set(os.listdir(source_node_modules)))
        self.assertNotIn("minimal-request-promise", set(os.listdir(source_node_modules)))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_download_dependencies_local_dependency(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "with-local-dependency")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"local-dependency", "minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_download_dependencies_and_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # source dependencies are symlinked to dependencies dir
        dependencies_dir_node_modules = os.path.join(self.dependencies_dir, "node_modules")
        self.assertTrue(os.path.islink(dependencies_dir_node_modules))
        self.assertEqual(read_link_without_junction_prefix(dependencies_dir_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_with_download_dependencies_and_dependencies_dir_without_combine_dependencies(
        self, runtime
    ):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to dependencies dir
        dependencies_dir_node_modules = os.path.join(self.dependencies_dir, "node_modules")
        self.assertTrue(os.path.islink(dependencies_dir_node_modules))
        self.assertEqual(read_link_without_junction_prefix(dependencies_dir_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_build_in_source_reuse_saved_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        # first build to save to dependencies_dir
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
        )

        # cleanup artifacts_dir to make sure we use dependencies from dependencies_dir
        for filename in os.listdir(self.artifacts_dir):
            file_path = os.path.join(self.artifacts_dir, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path)

        # build again without downloading dependencies
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # source dependencies are symlinked to dependencies dir
        dependencies_dir_node_modules = os.path.join(self.dependencies_dir, "node_modules")
        self.assertTrue(os.path.islink(dependencies_dir_node_modules))
        self.assertEqual(read_link_without_junction_prefix(dependencies_dir_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root(self, runtime):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies
        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_with_reuse_saved_dependencies_dir(self, runtime):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")
        expected_modules = {"minimal-request-promise"}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
        )

        # expected dependencies in dependencies directory
        dependencies_dir_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertEqual(expected_modules, dependencies_dir_modules)

        # cleanup artifacts_dir to make sure we use dependencies from dependencies_dir
        for filename in os.listdir(self.artifacts_dir):
            file_path = os.path.join(self.artifacts_dir, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path)

        # build again without downloading dependencies
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_with_dependencies_dir_and_not_combine(self, runtime):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")
        expected_modules = {"minimal-request-promise"}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies in dependencies directory
        dependencies_dir_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertEqual(expected_modules, dependencies_dir_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_with_dependencies_dir_and_combine(self, runtime):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root")
        source_dir = os.path.join(base_dir, "src")
        expected_modules = {"minimal-request-promise"}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=True,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies in dependencies directory
        artifacts_dir_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, artifacts_dir_modules)

        # expected dependencies in dependencies directory
        dependencies_dir_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertEqual(expected_modules, dependencies_dir_modules)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_and_local_dependencies(self, runtime):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root-with-local-dependency")
        source_dir = os.path.join(base_dir, "src")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            build_in_source=True,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies in artifact directory
        expected_modules = {"minimal-request-promise", "local-dependency", "axios"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertTrue(all(expected_module in output_modules for expected_module in expected_modules))

        # expected dependencies in source directory
        source_modules = set(os.listdir(os.path.join(source_dir, "node_modules")))
        self.assertTrue(all(expected_module in source_modules for expected_module in expected_modules))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_and_local_dependencies_with_reuse_saved_dependencies_dir(
        self, runtime
    ):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root-with-local-dependency")
        source_dir = os.path.join(base_dir, "src")
        expected_modules = {"minimal-request-promise", "local-dependency", "axios"}

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
        )

        # expected dependencies in dependencies directory
        dependencies_dir_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertTrue(all(expected_module in dependencies_dir_modules for expected_module in expected_modules))

        # cleanup artifacts_dir to make sure we use dependencies from dependencies_dir
        for filename in os.listdir(self.artifacts_dir):
            file_path = os.path.join(self.artifacts_dir, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path)

        # build again without downloading dependencies
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies in artifacts directory
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertTrue(all(expected_module in output_modules for expected_module in expected_modules))

        # expected dependencies in source directory
        source_modules = set(os.listdir(os.path.join(source_dir, "node_modules")))
        self.assertTrue(all(expected_module in source_modules for expected_module in expected_modules))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_and_local_dependencies_with_dependencies_dir_and_not_combine(
        self, runtime
    ):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root-with-local-dependency")
        source_dir = os.path.join(base_dir, "src")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies in dependencies directory
        expected_modules = {"minimal-request-promise", "local-dependency", "axios"}
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertTrue(all(expected_module in output_modules for expected_module in expected_modules))

        # expected dependencies in source directory
        source_modules = set(os.listdir(os.path.join(source_dir, "node_modules")))
        self.assertTrue(all(expected_module in source_modules for expected_module in expected_modules))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_builds_project_with_manifest_outside_root_and_local_dependencies_with_dependencies_dir_and_combine(
        self, runtime
    ):
        base_dir = os.path.join(self.temp_testdata_dir, "manifest-outside-root-with-local-dependency")
        source_dir = os.path.join(base_dir, "src")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(base_dir, "manifest", "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=True,
        )

        # expected output
        expected_files = {"package.json", "included.js", "excluded.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        # expected dependencies in dependencies directory
        expected_modules = {"minimal-request-promise", "local-dependency", "axios"}
        dependencies_dir_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertTrue(all(expected_module in dependencies_dir_modules for expected_module in expected_modules))

        # expected dependencies in artifacts directory
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertTrue(all(expected_module in output_modules for expected_module in expected_modules))

        # expected dependencies in source directory
        source_modules = set(os.listdir(os.path.join(source_dir, "node_modules")))
        self.assertTrue(all(expected_module in source_modules for expected_module in expected_modules))

    @parameterized.expand(SUPPORTED_RUNTIMES)
    @mock.patch.dict("os.environ", {"SAM_NPM_RUN_TEST_WITH_BUILD": "true"})
    def test_runs_test_script_if_specified(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "test-script-to-create-file")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "created.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_does_not_run_test_script_if_env_var_not_specified(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "test-script-to-create-file")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_does_not_raise_error_if_empty_test_script(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "empty-test-script")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)


class TestNodejsNpmInstallSharedDependencies(TestCase):
    """
    Runs LambdaBuilder.install_shared_dependencies against the real npm: one install at the
    workspace root prepares every member for builds that run with download_dependencies=False,
    which is how sam build uses it for an npm workspaces monorepo under --build-in-source.
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")
    SUPPORTED_RUNTIMES = [(runtime,) for runtime in NODEJS_RUNTIMES]

    def setUp(self):
        self.scratch_dir = tempfile.mkdtemp()
        self.fn_artifacts_dir = tempfile.mkdtemp()
        self.other_artifacts_dir = tempfile.mkdtemp()

        # use this so tests don't modify actual testdata, and we can parallelize
        self.temp_dir = tempfile.mkdtemp()
        self.temp_testdata_dir = os.path.join(self.temp_dir, "testdata")
        shutil.copytree(self.TEST_DATA_FOLDER, self.temp_testdata_dir)
        self.monorepo_dir = os.path.join(self.temp_testdata_dir, "workspaces-monorepo")

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm", application_framework=None)

    def tearDown(self):
        for directory in (self.scratch_dir, self.fn_artifacts_dir, self.other_artifacts_dir, self.temp_dir):
            shutil.rmtree(directory)

    def install_shared(self, project_root):
        # gated on the same flag the per-function builds below pass
        self.builder.install_shared_dependencies(project_root, experimental_flags=["experimentalNodejsMonorepo"])

    def build_member(self, endpoint, artifacts_dir, runtime):
        source_dir = os.path.join(self.monorepo_dir, "endpoints", endpoint)
        self.builder.build(
            source_dir,
            artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            download_dependencies=False,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

    @parameterized.expand(SUPPORTED_RUNTIMES)
    def test_installs_once_at_the_root_then_builds_members_without_downloading(self, runtime):
        lockfile_path = os.path.join(self.monorepo_dir, "package-lock.json")
        with open(lockfile_path, "rb") as lockfile:
            original_lockfile = lockfile.read()

        self.install_shared(self.monorepo_dir)

        # the lockfile drove the install: it pins 1.3.0 while the manifest range allows newer
        installed_manifest = os.path.join(self.monorepo_dir, "node_modules", "minimal-request-promise", "package.json")
        with open(installed_manifest) as manifest:
            self.assertEqual(json.load(manifest)["version"], "1.3.0")
        # and came back byte-identical
        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

        # both members build off that one install, downloading nothing themselves
        self.build_member("fn", self.fn_artifacts_dir, runtime)
        self.build_member("other", self.other_artifacts_dir, runtime)

        # npm kept everything hoisted: the builds added no node_modules beside the members
        self.assertFalse(os.path.exists(os.path.join(self.monorepo_dir, "endpoints", "fn", "node_modules")))
        self.assertFalse(os.path.exists(os.path.join(self.monorepo_dir, "endpoints", "other", "node_modules")))

        # each member's artifacts hold its own dependencies plus the workspace package, and not
        # its sibling's, even though npm hoisted both into the same root node_modules
        fn_modules = set(os.listdir(os.path.join(self.fn_artifacts_dir, "node_modules")))
        self.assertIn("minimal-request-promise", fn_modules)
        self.assertIn("@nodejs-workspaces-monorepo", fn_modules)
        self.assertNotIn("ms", fn_modules)

        other_modules = set(os.listdir(os.path.join(self.other_artifacts_dir, "node_modules")))
        self.assertIn("ms", other_modules)
        self.assertNotIn("minimal-request-promise", other_modules)

        # the handlers' own requires resolve from each artifacts directory
        for artifacts_dir in (self.fn_artifacts_dir, self.other_artifacts_dir):
            require_handler = subprocess.run(
                ["node", "-e", "require('./included.js')"],
                cwd=artifacts_dir,
                capture_output=True,
                text=True,
            )
            self.assertEqual(require_handler.returncode, 0, require_handler.stderr)

    def test_shared_install_without_a_lockfile_keeps_the_root_dev_dependencies(self):
        os.remove(os.path.join(self.monorepo_dir, "package-lock.json"))

        # a build tool the root depends on, spelled as a local file dependency so the assertion
        # does not ride on what the registry serves
        devtool_dir = os.path.join(self.monorepo_dir, "devtool")
        os.makedirs(devtool_dir)
        with open(os.path.join(devtool_dir, "package.json"), "w") as manifest:
            json.dump({"name": "devtool", "version": "1.0.0"}, manifest)

        root_manifest_path = os.path.join(self.monorepo_dir, "package.json")
        with open(root_manifest_path) as manifest:
            root_manifest = json.load(manifest)
        root_manifest["devDependencies"] = {"devtool": "file:devtool"}
        with open(root_manifest_path, "w") as manifest:
            json.dump(root_manifest, manifest)

        self.install_shared(self.monorepo_dir)

        # the shared install must not pass --omit=dev: run at the root that flag would remove the
        # root's own build tools, which the function builds still need
        self.assertTrue(os.path.isdir(os.path.join(self.monorepo_dir, "node_modules", "devtool")))
        # and one update still resolved every member's dependencies
        self.assertTrue(os.path.isdir(os.path.join(self.monorepo_dir, "node_modules", "ms")))
        self.assertTrue(os.path.isdir(os.path.join(self.monorepo_dir, "node_modules", "minimal-request-promise")))

    def test_shared_install_drops_a_dependency_removed_from_a_member_manifest(self):
        # aws/aws-lambda-builders#579 moved build-in-source to `npm update` because the install then in
        # use left a dependency behind after it was removed from the manifest. The shared install reaches
        # the same get_install_action, so it has to keep that property at the workspace root, where the
        # tree it reconciles is every member's at once. Asserted for both commands the action can pick:
        # with the lockfile (npm install) and then without one (npm update).
        lockfile_path = os.path.join(self.monorepo_dir, "package-lock.json")
        other_manifest_path = os.path.join(self.monorepo_dir, "endpoints", "other", "package.json")
        root_modules = os.path.join(self.monorepo_dir, "node_modules")

        def set_other_dependencies(dependencies):
            with open(other_manifest_path) as manifest:
                other_manifest = json.load(manifest)
            other_manifest["dependencies"] = dependencies
            with open(other_manifest_path, "w") as manifest:
                json.dump(other_manifest, manifest)

        self.install_shared(self.monorepo_dir)
        self.assertTrue(os.path.isdir(os.path.join(root_modules, "ms")), "the fixture's own dependency is missing")
        with open(lockfile_path, "rb") as lockfile:
            original_lockfile = lockfile.read()

        # the developer drops the dependency from the member that declared it, and rebuilds
        set_other_dependencies({})
        self.install_shared(self.monorepo_dir)

        self.assertFalse(
            os.path.exists(os.path.join(root_modules, "ms")),
            "the hoisted tree kept a dependency no member declares any more (#579)",
        )
        # still the developer's own directory, so the now out-of-date lockfile stays as they left it
        with open(lockfile_path, "rb") as lockfile:
            self.assertEqual(lockfile.read(), original_lockfile)

        # and the same holds on the no-lockfile path, which runs npm update instead of npm install
        os.remove(lockfile_path)
        set_other_dependencies({"ms": "^2.1.3"})
        self.install_shared(self.monorepo_dir)
        self.assertTrue(os.path.isdir(os.path.join(root_modules, "ms")))

        set_other_dependencies({})
        self.install_shared(self.monorepo_dir)

        self.assertFalse(
            os.path.exists(os.path.join(root_modules, "ms")),
            "the npm update path kept a dependency no member declares any more (#579)",
        )

    def test_a_failing_install_raises_the_error_the_caller_falls_back_on(self):
        # broken-deps pins a version the registry does not have, so the real npm install fails
        broken_dir = os.path.join(self.temp_testdata_dir, "broken-deps")

        with self.assertRaises(SharedDependenciesInstallError) as raised:
            self.install_shared(broken_dir)

        self.assertIn(broken_dir, str(raised.exception))

    def test_an_unflagged_caller_is_refused_and_installs_nothing(self):
        # the per-function build gates its artifacts link on experimentalNodejsMonorepo, so a caller
        # that installs without it would ship functions whose artifacts carry no dependencies
        with self.assertRaises(SharedDependenciesInstallError) as raised:
            self.builder.install_shared_dependencies(self.monorepo_dir)

        self.assertIn("experimentalNodejsMonorepo", str(raised.exception))
        self.assertFalse(os.path.exists(os.path.join(self.monorepo_dir, "node_modules")))
