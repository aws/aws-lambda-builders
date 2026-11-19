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
from aws_lambda_builders.exceptions import SharedProjectPreparationError
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmLinkDependencyClosureAction,
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
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest_and_build_in_source(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("not_source", "package-lock.json")

        self.osutils.dirname.return_value = "not_source"
        self.osutils.file_exists.return_value = True

        self.osutils.file_exists.side_effect = [True, False, False]
        # npm reports the install directory itself as its project root for anything that is not a
        # workspace member, which is what leaves the artifacts link pointing at the source tree
        resolve_project_root_mock.return_value = "not_source"

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
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_build_in_source_without_download_dependencies_and_without_dependencies_dir(
        self, resolve_project_root_mock, can_use_links_mock
    ):
        # Skipping the install does not mean skipping the dependencies: building in source, they are already
        # in the source tree, put there by whoever ran the install. The artifacts still have to be linked to
        # them, or this produces a deployment package with no node_modules at all.
        can_use_links_mock.return_value = True
        resolve_project_root_mock.return_value = "source"

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

        self.assertEqual(len(workflow.actions), 5)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], LinkSinglePathAction)
        self.assertEqual(workflow.actions[3]._source, os.path.join(source_dir, "node_modules"))
        self.assertEqual(workflow.actions[3]._dest, os.path.join(artifacts_dir, "node_modules"))
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_build_in_source_without_download_dependencies_narrows_a_monorepo_to_the_closure(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        # The install being skipped is exactly how a workspaces monorepo is built once the dependencies are
        # installed at the root, so this path has to narrow to the function's own closure too rather than
        # link the shared tree carrying every sibling's dependencies.
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("monorepo", "package-lock.json")
        resolve_project_root_mock.return_value = "monorepo"
        self.osutils.dirname.return_value = os.path.join("monorepo", "endpoints", "a")

        workflow = NodejsNpmWorkflow(
            source_dir=os.path.join("monorepo", "endpoints", "a"),
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path=os.path.join("monorepo", "endpoints", "a", "manifest"),
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
            download_dependencies=False,
        )

        closure_actions = [
            action for action in workflow.actions if isinstance(action, NodejsNpmLinkDependencyClosureAction)
        ]
        self.assertEqual(len(closure_actions), 1)
        self.assertEqual(closure_actions[0]._install_dir, os.path.join("monorepo", "endpoints", "a"))
        self.assertEqual(closure_actions[0]._project_root, "monorepo")

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_build_in_source_with_download_dependencies(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("source", "package-lock.json")

        source_dir = "source"
        artifacts_dir = "artifacts"
        # npm reports the install directory itself as its project root for anything that is not a
        # workspace member, which is what leaves the artifacts link pointing at the source tree
        resolve_project_root_mock.return_value = source_dir

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
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_build_in_source_links_artifacts_to_the_hoisted_dependencies_in_a_workspaces_monorepo(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        # npm hoists a workspace package's dependencies to the monorepo root it reports as its project
        # root, so that - not the function directory - is where the artifacts have to be linked
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("monorepo", "package-lock.json")
        resolve_project_root_mock.return_value = "monorepo"
        self.osutils.dirname.return_value = os.path.join("monorepo", "endpoints", "a")

        workflow = NodejsNpmWorkflow(
            source_dir=os.path.join("monorepo", "endpoints", "a"),
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path=os.path.join("monorepo", "endpoints", "a", "manifest"),
            osutils=self.osutils,
            build_in_source=True,
            experimental_flags=["experimentalNodejsMonorepo"],
        )

        # a workspaces monorepo gets the closure action instead of a link to the whole installed tree,
        # which would carry every sibling function's dependencies into this function's artifacts
        closure_actions = [
            action for action in workflow.actions if isinstance(action, NodejsNpmLinkDependencyClosureAction)
        ]
        self.assertEqual(len(closure_actions), 1)
        self.assertEqual(closure_actions[0]._install_dir, os.path.join("monorepo", "endpoints", "a"))
        self.assertEqual(closure_actions[0]._project_root, "monorepo")
        self.assertEqual(closure_actions[0]._artifacts_dir, "artifacts")
        self.assertFalse(
            [
                action
                for action in workflow.actions
                if isinstance(action, LinkSinglePathAction)
                and action._dest == os.path.join("artifacts", "node_modules")
            ]
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_without_the_flag_a_monorepo_keeps_the_plain_link_and_npm_is_not_asked(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        # the rollout guarantee: the same monorepo shape without the flag takes the link every release so
        # far has taken - the #933 gap - and npm is never asked where its project root is
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = None
        self.osutils.dirname.return_value = os.path.join("monorepo", "endpoints", "a")

        workflow = NodejsNpmWorkflow(
            source_dir=os.path.join("monorepo", "endpoints", "a"),
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path=os.path.join("monorepo", "endpoints", "a", "manifest"),
            osutils=self.osutils,
            build_in_source=True,
        )

        resolve_project_root_mock.assert_not_called()
        self.assertFalse(
            [action for action in workflow.actions if isinstance(action, NodejsNpmLinkDependencyClosureAction)]
        )
        self.assertTrue(
            [
                action
                for action in workflow.actions
                if isinstance(action, LinkSinglePathAction)
                and action._dest == os.path.join("artifacts", "node_modules")
            ]
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_lockfile_path")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_build_in_source_links_artifacts_to_the_source_when_npm_cannot_be_asked(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        # no answer from npm is no evidence the dependencies went anywhere else, so keep the old source
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = None
        resolve_project_root_mock.return_value = None

        source_dir = "source"
        workflow = NodejsNpmWorkflow(
            source_dir=source_dir,
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
        )

        links = [
            action
            for action in workflow.actions
            if isinstance(action, LinkSinglePathAction) and action._dest == os.path.join("artifacts", "node_modules")
        ]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]._source, os.path.join(source_dir, "node_modules"))

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
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm.resolve_project_root")
    def test_build_in_source_with_download_dependencies_and_dependencies_dir(
        self, resolve_project_root_mock, can_use_links_mock, get_lockfile_path_mock
    ):
        can_use_links_mock.return_value = True
        get_lockfile_path_mock.return_value = os.path.join("source", "package-lock.json")

        source_dir = "source"
        artifacts_dir = "artifacts"
        # npm reports the install directory itself as its project root for anything that is not a
        # workspace member, which is what leaves the artifacts link pointing at the source tree
        resolve_project_root_mock.return_value = source_dir

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
        # With the install skipped and a dependencies_dir to take dependencies from, the copy below is the
        # only supplier and there must be no link to the source tree. A link here would place a symlink at
        # artifacts/node_modules that the copy either silently keeps - pointing the artifacts at the source
        # tree instead of at the cached dependencies - or, when the cached node_modules is a real directory,
        # recurses through, writing the cached dependencies into the customer's source tree.
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
        self.assertFalse(
            [
                action
                for action in workflow.actions
                if isinstance(action, (LinkSinglePathAction, NodejsNpmLinkDependencyClosureAction))
            ]
        )

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
        self.subprocess_npm.resolve_project_root.return_value = os.path.join(self.tmp_dir, *path_parts)

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

    def test_asks_npm_for_the_project_root_of_the_install_dir(self):
        self._touch("fn", "package.json")
        self._npm_prefix_is("fn")

        self._lockfile_path(["fn"])

        self.subprocess_npm.resolve_project_root.assert_called_with(os.path.join(self.tmp_dir, "fn"))

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
        self.subprocess_npm.resolve_project_root.return_value = None

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


class TestNodejsNpmWorkflowInSourceDevDependencies(TestCase):
    """
    An in-source install at a workspace member reconciles the monorepo root's hoisted tree, so
    --omit=dev there deletes the ROOT's own devDependencies out of the customer's node_modules:
    aws/aws-sam-cli#6491. These pin which installs stop passing it, and which keep passing it.
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
        self.subprocess_npm.resolve_project_root.return_value = os.path.join(self.tmp_dir, *path_parts)

    def _install_action(
        self,
        install_dir,
        is_building_in_source=True,
        experimental_flags=("experimentalNodejsMonorepo",),
        omit_dev=True,
    ):
        return NodejsNpmWorkflow.get_install_action(
            source_dir=os.path.join(self.tmp_dir, install_dir),
            install_dir=os.path.join(self.tmp_dir, install_dir),
            subprocess_npm=self.subprocess_npm,
            osutils=self.osutils,
            build_options=None,
            is_building_in_source=is_building_in_source,
            experimental_flags=list(experimental_flags),
            omit_dev=omit_dev,
        )

    def test_a_workspace_member_install_keeps_dev_dependencies(self):
        # npm reports the monorepo root for a member, so the install reconciles a tree the build does
        # not own and must not prune
        self._touch("package.json")
        self._touch("endpoints", "a", "package.json")
        self._npm_prefix_is()

        action = self._install_action(install_dir=os.path.join("endpoints", "a"))

        self.assertIsInstance(action, NodejsNpmUpdateAction)
        self.assertFalse(action.omit_dev)

    def test_the_lockfile_install_at_a_member_keeps_dev_dependencies_too(self):
        # the same decision has to hold on the other branch of get_install_action
        self._touch("package.json")
        self._touch("package-lock.json")
        self._touch("endpoints", "a", "package.json")
        self._npm_prefix_is()

        action = self._install_action(install_dir=os.path.join("endpoints", "a"))

        self.assertIsInstance(action, NodejsNpmInstallAction)
        self.assertFalse(action.omit_dev)

    def test_a_standalone_project_still_omits_dev(self):
        # npm's project root is the install directory itself: there is no enclosing tree to damage, and
        # pruning keeps dev dependencies out of the artifacts the cheap way
        self._touch("fn", "package.json")
        self._npm_prefix_is("fn")

        action = self._install_action(install_dir="fn")

        self.assertTrue(action.omit_dev)

    def test_without_the_flag_a_member_install_still_omits_dev(self):
        # the rollout guarantee: no behaviour change until the caller opts in
        self._touch("package.json")
        self._touch("endpoints", "a", "package.json")
        self._npm_prefix_is()

        action = self._install_action(install_dir=os.path.join("endpoints", "a"), experimental_flags=())

        self.assertTrue(action.omit_dev)

    def test_a_build_that_is_not_in_source_still_omits_dev(self):
        # that install lands in a scratch directory the build does own, so pruning is right there and
        # npm is not even asked where the project root is
        self._touch("package.json")
        self._touch("endpoints", "a", "package.json")
        self._npm_prefix_is()

        action = self._install_action(install_dir=os.path.join("endpoints", "a"), is_building_in_source=False)

        self.assertTrue(action.omit_dev)
        self.subprocess_npm.resolve_project_root.assert_not_called()

    def test_omit_dev_false_is_left_alone(self):
        # the shared install at a workspace root already passes False; nothing here may turn it back on
        self._touch("package.json")
        self._npm_prefix_is()

        action = self._install_action(install_dir=".", omit_dev=False)

        self.assertFalse(action.omit_dev)

    def test_an_unanswerable_project_root_still_omits_dev(self):
        # npm could not be asked, so there is no evidence of an enclosing tree and the old behaviour stands
        self._touch("fn", "package.json")
        self.subprocess_npm.resolve_project_root.return_value = None

        action = self._install_action(install_dir="fn")

        self.assertTrue(action.omit_dev)


class TestNodejsNpmWorkflowEnclosingProjectRoot(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        self.subprocess_npm = Mock()

    def test_reports_a_root_above_the_install_dir(self):
        member = os.path.join(self.tmp_dir, "endpoints", "a")
        self.subprocess_npm.resolve_project_root.return_value = self.tmp_dir

        self.assertEqual(NodejsNpmWorkflow.enclosing_project_root(member, self.subprocess_npm), self.tmp_dir)

    def test_reports_none_when_the_install_dir_is_the_root(self):
        self.subprocess_npm.resolve_project_root.return_value = self.tmp_dir

        self.assertIsNone(NodejsNpmWorkflow.enclosing_project_root(self.tmp_dir, self.subprocess_npm))

    def test_reports_none_when_npm_could_not_be_asked(self):
        self.subprocess_npm.resolve_project_root.return_value = None

        self.assertIsNone(NodejsNpmWorkflow.enclosing_project_root(self.tmp_dir, self.subprocess_npm))

    def test_a_path_that_differs_only_by_case_or_separator_is_the_root(self):
        # npm answers with the resolved path while the caller may hold another spelling of it; comparing
        # the strings raw would read the same directory as an enclosing root and keep dev dependencies
        # in a standalone project
        spelled_differently = os.path.join(self.tmp_dir, "fn", "..", "fn")
        os.makedirs(os.path.join(self.tmp_dir, "fn"), exist_ok=True)
        self.subprocess_npm.resolve_project_root.return_value = os.path.join(self.tmp_dir, "fn")

        self.assertIsNone(NodejsNpmWorkflow.enclosing_project_root(spelled_differently, self.subprocess_npm))


class TestNodejsNpmWorkflowTestActionNotice(TestCase):
    """
    NodejsNpmTestAction rides along with the install, so a build that installs nothing runs no tests.
    That is not new, but the shared install makes it the normal path for a grouped function, and a
    silent skip looks exactly like a passing test suite.
    """

    def setUp(self):
        self.osutils = Mock()
        self.osutils.pipe = "PIPE"
        self.osutils.dirname.return_value = "source"

    def _workflow(self, download_dependencies):
        return NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            download_dependencies=download_dependencies,
        )

    @patch.dict("os.environ", {"SAM_NPM_RUN_TEST_WITH_BUILD": "true"})
    def test_says_so_when_tests_were_asked_for_but_no_install_will_run_them(self):
        # the logger is patched rather than captured with assertLogs: handler and level state is
        # global, so capturing it makes this test depend on what ran before it
        with patch("aws_lambda_builders.workflows.nodejs_npm.workflow.LOG") as log_mock:
            workflow = self._workflow(download_dependencies=False)

        self.assertFalse(any(isinstance(action, NodejsNpmTestAction) for action in workflow.actions))
        logged = " ".join(str(args) for args, _ in log_mock.info.call_args_list)
        self.assertIn("SAM_NPM_RUN_TEST_WITH_BUILD", logged, "nothing told the user their tests were skipped")
        self.assertIn("not run", logged)

    @patch.dict("os.environ", {"SAM_NPM_RUN_TEST_WITH_BUILD": "true"})
    def test_stays_quiet_when_the_build_does_install_and_so_does_run_them(self):
        workflow = self._workflow(download_dependencies=True)

        self.assertTrue(any(isinstance(action, NodejsNpmTestAction) for action in workflow.actions))

    @patch.dict("os.environ", {}, clear=True)
    def test_stays_quiet_when_tests_were_never_asked_for(self):
        # the default: no notice belongs in a build that was never going to run tests
        with patch("aws_lambda_builders.workflows.nodejs_npm.workflow.LOG") as log_mock:
            self._workflow(download_dependencies=False)

        log_mock.info.assert_not_called()


class TestNodejsNpmWorkflowPrepareSharedProject(TestCase):
    """
    the shared (once per workspace root) install reuses get_install_action, so these tests only pin
    what differs: it refuses without experimentalNodejsMonorepo, the root's dev dependencies
    survive, and failure maps to the typed error the caller falls back on
    """

    def setUp(self):
        self.osutils = OSUtils()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        self.subprocess_npm = Mock()
        self.subprocess_npm.resolve_project_root.return_value = self.tmp_dir

    def _touch(self, name):
        with open(os.path.join(self.tmp_dir, name), "w") as f:
            f.write("{}")

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_installs_at_the_root_honouring_the_lockfile_and_keeping_dev_dependencies(self, can_use_install_links):
        can_use_install_links.return_value = True
        self._touch("package.json")
        self._touch("package-lock.json")

        NodejsNpmWorkflow.prepare_shared_project(
            self.tmp_dir,
            experimental_flags=["experimentalNodejsMonorepo"],
            osutils=self.osutils,
            subprocess_npm=self.subprocess_npm,
        )

        # no --omit=dev: the root's own devDependencies (build tools like esbuild) must survive
        self.subprocess_npm.run.assert_called_with(
            ["install", "-q", "--no-audit", "--no-save", "--install-links"], cwd=self.tmp_dir
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_updates_when_the_root_has_no_lockfile(self, can_use_install_links):
        can_use_install_links.return_value = True
        self._touch("package.json")

        NodejsNpmWorkflow.prepare_shared_project(
            self.tmp_dir,
            experimental_flags=["experimentalNodejsMonorepo"],
            osutils=self.osutils,
            subprocess_npm=self.subprocess_npm,
        )

        self.subprocess_npm.run.assert_called_with(
            ["update", "--no-audit", "--no-save", "--no-package-lock", "--install-links"], cwd=self.tmp_dir
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_refuses_an_npm_without_install_links(self, can_use_install_links):
        can_use_install_links.return_value = False

        with self.assertRaises(SharedProjectPreparationError):
            NodejsNpmWorkflow.prepare_shared_project(
                self.tmp_dir,
                experimental_flags=["experimentalNodejsMonorepo"],
                osutils=self.osutils,
                subprocess_npm=self.subprocess_npm,
            )

        self.subprocess_npm.run.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_wraps_a_failed_install_in_the_typed_error(self, can_use_install_links):
        can_use_install_links.return_value = True
        self._touch("package.json")
        self._touch("package-lock.json")
        self.subprocess_npm.run.side_effect = NpmExecutionError(message="registry unreachable")

        with self.assertRaises(SharedProjectPreparationError):
            NodejsNpmWorkflow.prepare_shared_project(
                self.tmp_dir,
                experimental_flags=["experimentalNodejsMonorepo"],
                osutils=self.osutils,
                subprocess_npm=self.subprocess_npm,
            )

    @parameterized.expand([(None,), ([],), (["experimentalSomethingElse"],)])
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_refuses_without_the_monorepo_flag(self, experimental_flags, can_use_install_links):
        # the per-function build gates its artifacts link on the same flag, so installing without it
        # would leave every function's artifacts empty
        can_use_install_links.return_value = True
        self._touch("package.json")
        self._touch("package-lock.json")

        with self.assertRaises(SharedProjectPreparationError):
            NodejsNpmWorkflow.prepare_shared_project(
                self.tmp_dir,
                experimental_flags=experimental_flags,
                osutils=self.osutils,
                subprocess_npm=self.subprocess_npm,
            )

        self.subprocess_npm.run.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_refuses_the_flag_before_asking_npm_its_version(self, can_use_install_links):
        # an unflagged caller must not pay for a subprocess just to be told no
        with self.assertRaises(SharedProjectPreparationError):
            NodejsNpmWorkflow.prepare_shared_project(
                self.tmp_dir, osutils=self.osutils, subprocess_npm=self.subprocess_npm
            )

        can_use_install_links.assert_not_called()
