import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import ANY, patch, call, Mock

from parameterized import parameterized

from aws_lambda_builders.actions import (
    CopySourceAction,
    CleanUpAction,
    CopyDependenciesAction,
    LinkSinglePathAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.architecture import ARM64
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmCIAction,
    NodejsNpmUpdateAction,
    NodejsNpmTestAction,
)


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestNodejsNpmWorkflow(TestCase):
    """
    the workflow requires an external utility (npm) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.osutils.dirname.return_value = "source"
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.osutils.is_windows.side_effect = [False]
        self.osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir(self):
        self.osutils.file_exists.return_value = True

        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "source/manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 7)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest(self):
        self.osutils.dirname.return_value = "not_source"
        self.osutils.file_exists.return_value = True

        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "not_source/manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 8)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertEqual(workflow.actions[3].source_dir, "source")
        self.assertEqual(workflow.actions[3].dest_dir, "artifacts")
        self.assertIsInstance(workflow.actions[4], NodejsNpmInstallAction)
        self.assertEqual(workflow.actions[4].install_dir, "artifacts")
        self.assertIsInstance(workflow.actions[5], NodejsNpmTestAction)
        self.assertEqual(workflow.actions[5].install_dir, "artifacts")
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmLockFileCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest_and_build_in_source(
        self, can_use_links_mock, get_lockfile_path_mock
    ):
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("not_source", "package-lock.json")

        self.osutils.dirname.return_value = "not_source"
        self.osutils.file_exists.return_value = True

        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "not_source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        self.assertEqual(len(workflow.actions), 9)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertEqual(workflow.actions[3].source_dir, "source")
        self.assertEqual(workflow.actions[3].dest_dir, "artifacts")
        self.assertIsInstance(workflow.actions[4], NodejsNpmInstallAction)
        self.assertTrue(workflow.actions[4].install_links)
        self.assertEqual(workflow.actions[4].install_dir, "not_source")
        self.assertIsInstance(workflow.actions[5], NodejsNpmTestAction)
        self.assertEqual(workflow.actions[5].install_dir, "not_source")
        self.assertIsInstance(workflow.actions[6], LinkSinglePathAction)
        self.assertEqual(workflow.actions[6]._source, os.path.join("not_source", "node_modules"))
        self.assertEqual(workflow.actions[6]._dest, os.path.join("source", "node_modules"))
        self.assertIsInstance(workflow.actions[7], LinkSinglePathAction)
        self.assertEqual(workflow.actions[7]._source, os.path.join("source", "node_modules"))
        self.assertEqual(workflow.actions[7]._dest, os.path.join("artifacts", "node_modules"))
        self.assertIsInstance(workflow.actions[8], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_with_dependencies_dir(self):
        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=False,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 7)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmLockFileCleanUpAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_bundler_if_manifest_doesnt_request_it(self):
        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "source/manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 7)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_and_dependencies_dir(self):
        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 10)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertIsInstance(workflow.actions[5], CleanUpAction)
        self.assertIsInstance(workflow.actions[6], CopyDependenciesAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[8], NodejsNpmLockFileCleanUpAction)
        self.assertIsInstance(workflow.actions[9], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_and_without_dependencies_dir(self):
        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir=None,
            download_dependencies=False,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_combine_dependencies(self):
        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 10)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertIsInstance(workflow.actions[5], CleanUpAction)
        self.assertIsInstance(workflow.actions[6], MoveDependenciesAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[8], NodejsNpmLockFileCleanUpAction)
        self.assertIsInstance(workflow.actions[9], NodejsNpmLockFileCleanUpAction)

    def test_must_validate_architecture(self):
        self.osutils.is_windows.side_effect = [False, False]
        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch",
            "source/manifest",
            options={"artifact_executable_name": "foo"},
            osutils=self.osutils,
        )
        workflow_with_arm = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch",
            "source/manifest",
            architecture=ARM64,
            osutils=self.osutils,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")

    def test_workflow_uses_npm_ci_if_shrinkwrap_exists_and_npm_ci_enabled(self):
        self.osutils.file_exists.side_effect = [True, False, True]

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            options={"use_npm_ci": True},
        )

        self.assertEqual(len(workflow.actions), 7)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmCIAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmLockFileCleanUpAction)
        self.osutils.file_exists.assert_has_calls(
            [call("source/package-lock.json"), call("source/npm-shrinkwrap.json")]
        )

    def test_workflow_uses_npm_ci_if_lockfile_exists_and_npm_ci_enabled(self):
        self.osutils.file_exists.side_effect = [True, True]

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            options={"use_npm_ci": True},
        )

        self.assertEqual(len(workflow.actions), 7)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmCIAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmLockFileCleanUpAction)
        self.osutils.file_exists.assert_has_calls([call("source/package-lock.json")])

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_build_in_source_without_download_dependencies_and_without_dependencies_dir(self, can_use_links_mock):
        can_use_links_mock.return_value = True

        source_dir = "source"
        artifacts_dir = "artifacts"
        workflow = NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            download_dependencies=False,
        )

        self.assertEqual(len(workflow.actions), 4)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmrcCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_build_in_source_with_download_dependencies(self, can_use_links_mock, get_lockfile_path_mock):
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("source", "package-lock.json")

        source_dir = "source"
        artifacts_dir = "artifacts"
        workflow = NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        self.assertEqual(len(workflow.actions), 7)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertTrue(workflow.actions[3].install_links)
        self.assertEqual(workflow.actions[3].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertEqual(workflow.actions[4].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[5], LinkSinglePathAction)
        self.assertEqual(workflow.actions[5]._source, os.path.join(source_dir, "node_modules"))
        self.assertEqual(workflow.actions[5]._dest, os.path.join(artifacts_dir, "node_modules"))
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_build_in_source_without_lockfile_keeps_updating_dependencies(
        self, can_use_links_mock, get_lockfile_path_mock
    ):
        # with no lockfile anywhere there are no locked versions to install, and `npm update` additionally
        # prunes dependencies that were removed from the manifest since the previous build. The flag is on so
        # that the lookup is reached at all - what selects the update here is the missing lockfile, not the flag
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = None

        source_dir = "source"
        workflow = NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        self.assertIsInstance(workflow.actions[3], NodejsNpmUpdateAction)
        self.assertEqual(workflow.actions[3].install_dir, source_dir)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_build_in_source_with_download_dependencies_and_dependencies_dir(
        self, can_use_links_mock, get_lockfile_path_mock
    ):
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("source", "package-lock.json")

        source_dir = "source"
        artifacts_dir = "artifacts"
        workflow = NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
            dependencies_dir="dep",
        )

        self.assertEqual(len(workflow.actions), 9)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertTrue(workflow.actions[3].install_links)
        self.assertEqual(workflow.actions[3].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[4], NodejsNpmTestAction)
        self.assertEqual(workflow.actions[4].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[5], LinkSinglePathAction)
        self.assertEqual(workflow.actions[5]._source, os.path.join(source_dir, "node_modules"))
        self.assertEqual(workflow.actions[5]._dest, os.path.join(artifacts_dir, "node_modules"))
        self.assertIsInstance(workflow.actions[6], CleanUpAction)
        self.assertIsInstance(workflow.actions[7], CopyDependenciesAction)
        self.assertIsInstance(workflow.actions[8], NodejsNpmrcCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_build_in_source_with_dependencies_dir(self, can_use_links_mock):
        can_use_links_mock.return_value = True

        source_dir = "source"
        artifacts_dir = "artifacts"
        workflow = NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            dependencies_dir="dep",
            download_dependencies=False,
        )

        self.assertEqual(len(workflow.actions), 5)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    @parameterized.expand(
        [
            ("8.8.0", True),
            ("8.9.0", True),
            ("8.7.0", False),
            ("7.9.0", False),
            ("9.9.0", True),
            ("1.2", False),
            ("8.8", True),
            ("foo", False),
            ("foo.bar", False),
            ("", False),
        ]
    )
    def test_npm_version_validation(self, returned_npm_version, expected_result):
        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "source/manifest")

        npm_subprocess = Mock()
        npm_subprocess.run = Mock(return_value=returned_npm_version)

        result = workflow.can_use_install_links(npm_subprocess)

        self.assertEqual(result, expected_result)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_install_action")
    def test_workflow_revert_build_in_source(self, install_action_mock, install_links_mock):
        # fake having bad npm version
        install_links_mock.return_value = False

        source_dir = "source"
        artifacts_dir = "artifacts"
        scratch_dir = "scratch_dir"
        NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir=scratch_dir,
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
            dependencies_dir="dep",
        )

        # expect no build in source and install dir is
        # artifacts, not the source
        install_action_mock.assert_called_with(
            source_dir=source_dir,
            install_dir=artifacts_dir,
            subprocess_npm=ANY,
            osutils=ANY,
            build_options=ANY,
            is_building_in_source=False,
            experimental_flags=["experimentalNodejsMonorepo"],
        )


class TestNodejsNpmWorkflowGetLockfilePath(TestCase):
    """
    the lockfile is looked for in the directory `npm prefix` names, so these tests use a real
    temporary directory tree with a stubbed npm
    """

    def setUp(self):
        self.osutils = OSUtils()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        self.subprocess_npm = Mock()

    def _touch(self, *path_parts):
        file_path = os.path.join(self.tmp_dir, *path_parts)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write("{}")
        return file_path

    def _npm_prefix_is(self, *path_parts):
        # npm prints the project root with a trailing newline
        self.subprocess_npm.run.return_value = os.path.join(self.tmp_dir, *path_parts) + os.linesep

    def _lockfile_path(self, install_dir_parts):
        return NodejsNpmWorkflow.get_lockfile_path(
            os.path.join(self.tmp_dir, *install_dir_parts), self.subprocess_npm, self.osutils
        )

    # the lockfile lookup is what this class is about, so it opts in by default; the flag-off case
    # gets its own test below
    def _install_action(self, source_dir, install_dir, experimental_flags=("experimentalNodejsMonorepo",)):
        return NodejsNpmWorkflow.get_install_action(
            source_dir=os.path.join(self.tmp_dir, source_dir),
            install_dir=os.path.join(self.tmp_dir, install_dir),
            subprocess_npm=self.subprocess_npm,
            osutils=self.osutils,
            build_options=None,
            is_building_in_source=True,
            experimental_flags=list(experimental_flags),
        )

    def test_asks_npm_for_the_project_root(self):
        self._touch("fn", "package.json")
        self._npm_prefix_is("fn")

        self._lockfile_path(["fn"])

        self.subprocess_npm.run.assert_called_with(["prefix"], cwd=os.path.join(self.tmp_dir, "fn"))

    def test_without_the_flag_a_lockfile_is_ignored_and_the_update_runs(self):
        # the rollout guarantee: a project with a lockfile npm would read still takes the update every
        # release so far has run, and npm is not even asked where the lockfile is
        self._touch("fn", "package.json")
        self._touch("fn", "package-lock.json")
        self._npm_prefix_is("fn")

        action = self._install_action(source_dir="fn", install_dir="fn", experimental_flags=())

        self.assertIsInstance(action, NodejsNpmUpdateAction)
        self.subprocess_npm.run.assert_not_called()

    def test_finds_lockfile_in_the_project_root(self):
        self._touch("fn", "package.json")
        lockfile = self._touch("fn", "package-lock.json")
        self._npm_prefix_is("fn")

        self.assertEqual(self._lockfile_path(["fn"]), lockfile)

    def test_finds_lockfile_at_the_workspaces_root(self):
        # for a workspace package npm reports the monorepo root, where the single lockfile lives
        self._touch("package.json")
        lockfile = self._touch("package-lock.json")
        self._touch("endpoints", "a", "package.json")
        self._npm_prefix_is()

        self.assertEqual(self._lockfile_path(["endpoints", "a"]), lockfile)

    def test_finds_shrinkwrap_at_the_workspaces_root(self):
        self._touch("package.json")
        shrinkwrap = self._touch("npm-shrinkwrap.json")
        self._touch("endpoints", "a", "package.json")
        self._npm_prefix_is()

        self.assertEqual(self._lockfile_path(["endpoints", "a"]), shrinkwrap)

    def test_prefers_the_shrinkwrap_when_the_project_root_has_both(self):
        # npm reads npm-shrinkwrap.json and ignores package-lock.json when both are present, measured on
        # npm 10.9.9 and 11.19.0 alike, so that is the file this reports
        self._touch("fn", "package.json")
        self._touch("fn", "package-lock.json")
        shrinkwrap = self._touch("fn", "npm-shrinkwrap.json")
        self._npm_prefix_is("fn")

        self.assertEqual(self._lockfile_path(["fn"]), shrinkwrap)

    def test_ignores_a_lockfile_outside_the_project_root(self):
        # a nested package that is not a declared workspace is its own project root, and npm does not read
        # an ancestor's lockfile for it
        self._touch("package.json")
        self._touch("package-lock.json")
        self._touch("src", "fn", "package.json")
        self._npm_prefix_is("src", "fn")

        self.assertIsNone(self._lockfile_path(["src", "fn"]))

    def test_returns_none_when_the_project_root_has_no_lockfile(self):
        self._touch("fn", "package.json")
        self._npm_prefix_is("fn")

        self.assertIsNone(self._lockfile_path(["fn"]))

    def test_returns_none_when_npm_cannot_report_the_project_root(self):
        self._touch("fn", "package.json")
        self._touch("fn", "package-lock.json")
        self.subprocess_npm.run.side_effect = NpmExecutionError(message="boom!")

        self.assertIsNone(self._lockfile_path(["fn"]))

    def test_install_action_reads_the_lockfile_of_an_external_manifest_directory(self):
        # building in source with an external manifest installs in the manifest directory, which is a sibling of
        # the source directory, so that is the directory npm resolves its project root from
        self._touch("src", "included.js")
        self._touch("manifest", "package.json")
        self._touch("manifest", "package-lock.json")
        self._npm_prefix_is("manifest")

        action = self._install_action(source_dir="src", install_dir="manifest")

        self.assertIsInstance(action, NodejsNpmInstallAction)
        self.assertTrue(action.install_links)

    def test_install_action_ignores_a_lockfile_outside_the_install_dir(self):
        # a lockfile beside the source code says nothing about the tree npm installs into
        self._touch("src", "package.json")
        self._touch("src", "package-lock.json")
        self._touch("manifest", "package.json")
        self._npm_prefix_is("manifest")

        action = self._install_action(source_dir="src", install_dir="manifest")

        self.assertIsInstance(action, NodejsNpmUpdateAction)
