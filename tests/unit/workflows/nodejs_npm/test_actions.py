import itertools
import json
import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch, call
from parameterized import parameterized

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmLinkDependencyClosureAction,
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmCIAction,
    NodejsNpmTestAction,
)
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils


class TestNodejsNpmPackAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.actions.extract_tarfile")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_tars_and_unpacks_npm_project(self, OSUtilMock, SubprocessNpmMock, extract_tarfile_mock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmPackAction(
            "artifacts", "scratch_dir", "manifest", osutils=osutils, subprocess_npm=subprocess_npm
        )

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        subprocess_npm.run.return_value = "package.tar"

        action.execute()

        subprocess_npm.run.assert_called_with(["pack", "-q", "file:/abs:/dir:manifest"], cwd="scratch_dir")
        extract_tarfile_mock.assert_called_with("scratch_dir/package.tar", "artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmPackAction(
            "artifacts", "scratch_dir", "manifest", osutils=osutils, subprocess_npm=subprocess_npm
        )

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmInstallAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_installs_npm_production_dependencies_for_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("artifacts", subprocess_npm=subprocess_npm)

        action.execute()

        expected_args = ["install", "-q", "--no-audit", "--no-save", "--omit=dev"]

        subprocess_npm.run.assert_called_with(expected_args, cwd="artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_installs_with_install_links_when_requested(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("source", subprocess_npm=subprocess_npm, install_links=True)

        action.execute()

        # deliberately no --no-package-lock: a project that has a lockfile gets the locked versions installed
        expected_args = ["install", "-q", "--no-audit", "--no-save", "--omit=dev", "--install-links"]

        subprocess_npm.run.assert_called_with(expected_args, cwd="source")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmInstallAction("artifacts", subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmCIAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmCIAction("sources", subprocess_npm=subprocess_npm)

        action.execute()

        subprocess_npm.run.assert_called_with(["ci"], cwd="sources")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmCIAction("sources", subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmrcAndLockfileCopyAction(TestCase):
    @parameterized.expand(itertools.product([True, False], [True, False], [True, False]))
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_copies_into_a_project_if_file_exists(
        self, npmrc_exists, package_lock_exists, shrinkwrap_exists, OSUtilMock
    ):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcAndLockfileCopyAction("artifacts", "source", osutils=osutils)
        osutils.file_exists.side_effect = [npmrc_exists, package_lock_exists, shrinkwrap_exists]
        action.execute()

        filename_exists = {
            ".npmrc": npmrc_exists,
            "package-lock.json": package_lock_exists,
            "npm-shrinkwrap.json": shrinkwrap_exists,
        }
        file_exists_calls = [call("source/{}".format(filename)) for filename in filename_exists]
        copy_file_calls = [
            call("source/{}".format(filename), "artifacts") for filename, exists in filename_exists.items() if exists
        ]
        osutils.file_exists.assert_has_calls(file_exists_calls)
        osutils.copy_file.assert_has_calls(copy_file_calls)

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_copying_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.copy_file.side_effect = OSError()

        action = NodejsNpmrcAndLockfileCopyAction("artifacts", "source", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmrcCleanUpAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_npmrc_if_npmrc_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/.npmrc")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_npmrc_removal_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_removing_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.remove_file.side_effect = OSError()

        action = NodejsNpmrcCleanUpAction("artifacts", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmLockFileCleanUpAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_dot_package_lock_if_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b, c: "{}/{}/{}".format(a, b, c)

        action = NodejsNpmLockFileCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/node_modules/.package-lock.json")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_lockfile_removal_if_it_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b, c: "{}/{}/{}".format(a, b, c)

        action = NodejsNpmLockFileCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_removing_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b, c: "{}/{}/{}".format(a, b, c)

        osutils.remove_file.side_effect = OSError()

        action = NodejsNpmLockFileCleanUpAction("artifacts", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmTestAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch.dict("os.environ", {"SAM_NPM_RUN_TEST_WITH_BUILD": "true"}, clear=True)
    def test_runs_npm_test_for_npm_project_if_env_var_true(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmTestAction(install_dir="tests", subprocess_npm=subprocess_npm)

        action.execute()

        expected_args = ["test", "--if-present"]

        subprocess_npm.run.assert_called_with(expected_args, cwd="tests")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_does_not_run_npm_test_for_npm_project_if_no_env_var(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmTestAction(install_dir="tests", subprocess_npm=subprocess_npm)

        action.execute()

        assert not subprocess_npm.run.called

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch.dict("os.environ", {"SAM_NPM_RUN_TEST_WITH_BUILD": "true"}, clear=True)
    def test_raises_action_failed_when_npm_test_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmTestAction("artifacts", subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmLinkDependencyClosureAction(TestCase):
    """
    the action places real directories under names npm reports, so these tests use a real temporary tree
    """

    def setUp(self):
        self.osutils = OSUtils()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        self.subprocess_npm = MagicMock()
        self.artifacts_dir = os.path.join(self.tmp_dir, "artifacts")
        os.makedirs(self.artifacts_dir)
        self.root = os.path.join(self.tmp_dir, "monorepo")
        self.install_dir = os.path.join(self.root, "endpoints", "fn")

    def _package(self, relative_path, name):
        path = os.path.join(self.root, *relative_path.split("/"))
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "package.json"), "w") as manifest:
            json.dump({"name": name, "version": "1.0.0"}, manifest)
        return path

    def _action(self):
        return NodejsNpmLinkDependencyClosureAction(
            install_dir=self.install_dir,
            project_root=self.root,
            artifacts_dir=self.artifacts_dir,
            subprocess_npm=self.subprocess_npm,
            osutils=self.osutils,
        )

    def _linked(self):
        node_modules = os.path.join(self.artifacts_dir, "node_modules")
        found = set()
        for entry in os.listdir(node_modules):
            if entry.startswith("@"):
                found.update(f"{entry}/{scoped}" for scoped in os.listdir(os.path.join(node_modules, entry)))
            else:
                found.add(entry)
        return found

    def test_links_only_this_function_s_dependencies(self):
        self._package("endpoints/fn", "@mono/fn")
        mine = self._package("node_modules/lodash", "lodash")
        siblings = self._package("node_modules/ms", "ms")
        self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, mine]

        self._action().execute()

        self.assertEqual(self._linked(), {"lodash"})
        self.assertTrue(os.path.exists(siblings), "the sibling's package must stay where npm put it")

    def test_links_a_workspace_dependency_under_its_own_name(self):
        # npm reports a workspace dependency as its source directory, whose basename is not the package name
        self._package("endpoints/fn", "@mono/fn")
        shared = self._package("packages/shared-impl", "@mono/shared")
        self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, shared]

        self._action().execute()

        self.assertEqual(self._linked(), {"@mono/shared"})

    def test_leaves_a_nested_copy_inside_the_dependency_that_pins_it(self):
        # hoisting a nested copy to the top level would shadow the top-level version for every caller
        self._package("endpoints/fn", "@mono/fn")
        dep = self._package("packages/dep", "@mono/dep")
        nested = self._package("packages/dep/node_modules/lodash", "lodash")
        hoisted = self._package("node_modules/lodash", "lodash")
        self.subprocess_npm.resolve_dependency_closure.return_value = [
            self.root,
            self.install_dir,
            dep,
            nested,
            hoisted,
        ]

        self._action().execute()

        self.assertEqual(self._linked(), {"@mono/dep", "lodash"})
        self.assertEqual(
            os.path.realpath(os.path.join(self.artifacts_dir, "node_modules", "lodash")),
            os.path.realpath(hoisted),
        )

    def test_links_the_whole_installed_tree_when_npm_cannot_be_asked(self):
        # an over-complete node_modules still runs; an empty one does not
        self._package("node_modules/lodash", "lodash")
        self._package("node_modules/ms", "ms")
        self.subprocess_npm.resolve_dependency_closure.return_value = None

        self._action().execute()

        self.assertEqual(self._linked(), {"lodash", "ms"})

    def test_the_fallback_carries_the_function_s_own_non_hoisted_dependencies(self):
        # the fallback is only sound if it is a SUPERSET: one link for project_root/node_modules is not,
        # because a member's conflicting version is installed under the member's own node_modules
        self._package("node_modules/lodash", "lodash")
        pinned = self._package("endpoints/fn/node_modules/lodash", "lodash")
        self._package("endpoints/fn/node_modules/only-mine", "only-mine")
        self.subprocess_npm.resolve_dependency_closure.return_value = None

        self._action().execute()

        self.assertEqual(self._linked(), {"lodash", "only-mine"})
        self.assertEqual(
            os.path.realpath(os.path.join(self.artifacts_dir, "node_modules", "lodash")),
            os.path.realpath(pinned),
            "the function's own copy is what its code resolves, so it wins over the hoisted one",
        )

    def test_the_fallback_links_nothing_rather_than_a_dangling_node_modules(self):
        # os.symlink succeeds against a missing target, so linking an absent tree used to leave a
        # node_modules pointing nowhere - worse than the no-op, because the artifacts copy then follows it
        self.subprocess_npm.resolve_dependency_closure.return_value = None

        self._action().execute()

        self.assertFalse(
            os.path.lexists(os.path.join(self.artifacts_dir, "node_modules")),
            "nothing was installed, so there is nothing to point at",
        )

    def test_an_aliased_dependency_keeps_the_name_npm_installed_it_under(self):
        # `"lodash4": "npm:lodash@^4.0.0"` installs at node_modules/lodash4 with a manifest still saying
        # "lodash"; taking the manifest name breaks require("lodash4") - this action's own failure mode
        self._package("endpoints/fn", "@mono/fn")
        alias = self._package("node_modules/lodash4", "lodash")
        self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, alias]

        self._action().execute()

        self.assertEqual(self._linked(), {"lodash4"})

    def test_the_function_s_own_pinned_copy_wins_a_name_it_shares_with_the_hoisted_one(self):
        # neither path is nested inside the other, so both reach the link step and used to race: whichever
        # npm printed first won, because create_symlink_or_copy returns early on an existing destination
        self._package("endpoints/fn", "@mono/fn")
        pinned = self._package("endpoints/fn/node_modules/lodash", "lodash")
        hoisted = self._package("node_modules/lodash", "lodash")
        for order in ([pinned, hoisted], [hoisted, pinned]):
            shutil.rmtree(os.path.join(self.artifacts_dir, "node_modules"), ignore_errors=True)
            self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, *order]

            self._action().execute()

            self.assertEqual(self._linked(), {"lodash"})
            self.assertEqual(
                os.path.realpath(os.path.join(self.artifacts_dir, "node_modules", "lodash")),
                os.path.realpath(pinned),
                f"the function's own copy must win whatever order npm reports ({order})",
            )

    def test_a_hostile_manifest_name_cannot_write_outside_the_artifacts(self):
        # the name of a workspace dependency is the one value still read from a manifest, so it is the one
        # that has to be refused rather than joined onto the destination
        self._package("endpoints/fn", "@mono/fn")
        for hostile in ("../../../evil", "/tmp/evil", "..", "a/b/c"):
            shutil.rmtree(os.path.join(self.artifacts_dir, "node_modules"), ignore_errors=True)
            shared = self._package("packages/shared-impl", hostile)
            self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, shared]

            with self.assertRaises(ActionFailedError) as raised:
                self._action().execute()

            self.assertIn(repr(hostile), str(raised.exception))
            self.assertFalse(
                os.path.exists(os.path.join(self.tmp_dir, "evil")),
                f"{hostile} must not have created anything outside the artifacts",
            )

    def test_fails_loudly_when_a_workspace_dependency_has_no_manifest(self):
        # outside node_modules the path carries no name, so the manifest is the only source and its
        # absence has to stop the build rather than guess one from the directory
        self._package("endpoints/fn", "@mono/fn")
        no_manifest = os.path.join(self.root, "packages", "mystery-impl")
        os.makedirs(no_manifest)
        self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, no_manifest]

        with self.assertRaises(ActionFailedError) as raised:
            self._action().execute()

        self.assertIn("mystery-impl", str(raised.exception))

    def test_a_package_under_node_modules_needs_no_manifest_at_all(self):
        # the path already carries the name, so an unreadable manifest is no longer a reason to fail
        self._package("endpoints/fn", "@mono/fn")
        no_manifest = os.path.join(self.root, "node_modules", "mystery")
        os.makedirs(no_manifest)
        self.subprocess_npm.resolve_dependency_closure.return_value = [self.root, self.install_dir, no_manifest]

        self._action().execute()

        self.assertEqual(self._linked(), {"mystery"})
