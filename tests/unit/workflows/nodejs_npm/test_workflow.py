import mock

from unittest import TestCase
from mock import patch, call

from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.actions import CopySourceAction, CleanUpAction, CopyDependenciesAction, MoveDependenciesAction
from aws_lambda_builders.architecture import ARM64
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.esbuild import SubprocessEsbuild
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmCIAction,
    EsbuildBundleAction,
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
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.osutils.is_windows.side_effect = [False]
        self.osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

    def test_workflow_fails_if_manifest_parsing_fails(self):

        self.osutils.parse_json.side_effect = OSError("boom!")

        with self.assertRaises(WorkflowFailedError) as raised:
            NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.assertEqual(raised.exception.args[0], "NodejsNpmBuilder:ParseManifest - boom!")

        self.osutils.parse_json.assert_called_with("manifest")

    def test_workflow_sets_up_npm_actions_without_bundler_if_manifest_doesnt_request_it(self):

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 6)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_and_dependencies_dir(self):

        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 8)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], CleanUpAction)
        self.assertIsInstance(workflow.actions[5], CopyDependenciesAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies_and_without_dependencies_dir(self):
        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir=None,
            download_dependencies=False,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_without_combine_dependencies(self):

        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 8)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], CleanUpAction)
        self.assertIsInstance(workflow.actions[5], MoveDependenciesAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_bundler_if_manifest_requests_it(self):

        self.osutils.parse_json.side_effect = [{"aws_sam": {"bundler": "esbuild"}}]

        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], NodejsNpmInstallAction)

        self.assertIsInstance(workflow.actions[1], EsbuildBundleAction)

        self.osutils.parse_json.assert_called_with("manifest")

        self.osutils.file_exists.assert_has_calls(
            [call("source/package-lock.json"), call("source/npm-shrinkwrap.json")]
        )

    def test_sets_up_esbuild_search_path_from_npm_bin(self):

        self.popen.out = b"project/bin"
        self.osutils.parse_json.side_effect = [{"aws_sam": {"bundler": "esbuild"}}]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.osutils.popen.assert_called_with(["npm", "bin"], stdout="PIPE", stderr="PIPE", cwd="source")

        esbuild = workflow.actions[1].subprocess_esbuild

        self.assertIsInstance(esbuild, SubprocessEsbuild)

        self.assertEqual(esbuild.executable_search_paths, ["project/bin"])

    def test_sets_up_esbuild_search_path_with_workflow_executable_search_paths_after_npm_bin(self):

        self.popen.out = b"project/bin"
        self.osutils.parse_json.side_effect = [{"aws_sam": {"bundler": "esbuild"}}]

        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            osutils=self.osutils,
            executable_search_paths=["other/bin"],
        )

        self.osutils.popen.assert_called_with(["npm", "bin"], stdout="PIPE", stderr="PIPE", cwd="source")

        esbuild = workflow.actions[1].subprocess_esbuild

        self.assertIsInstance(esbuild, SubprocessEsbuild)

        self.assertEqual(esbuild.executable_search_paths, ["project/bin", "other/bin"])

    def test_workflow_uses_npm_ci_if_lockfile_exists(self):

        self.osutils.parse_json.side_effect = [{"aws_sam": {"bundler": "esbuild"}}]
        self.osutils.file_exists.side_effect = [True, True]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], NodejsNpmCIAction)

        self.assertIsInstance(workflow.actions[1], EsbuildBundleAction)

        self.osutils.file_exists.assert_has_calls([call("source/package-lock.json")])

    def test_workflow_uses_npm_ci_if_shrinkwrap_exists(self):

        self.osutils.parse_json.side_effect = [{"aws_sam": {"bundler": "esbuild"}}]
        self.osutils.file_exists.side_effect = [True, False, True]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], NodejsNpmCIAction)

        self.assertIsInstance(workflow.actions[1], EsbuildBundleAction)

        self.osutils.file_exists.assert_has_calls(
            [call("source/package-lock.json"), call("source/npm-shrinkwrap.json")]
        )

    def test_must_validate_architecture(self):
        self.osutils.is_windows.side_effect = [False, False]
        workflow = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
            osutils=self.osutils,
        )
        workflow_with_arm = NodejsNpmWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            architecture=ARM64,
            osutils=self.osutils,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")
