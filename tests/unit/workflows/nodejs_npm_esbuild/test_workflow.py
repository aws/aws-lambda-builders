import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import ANY, patch, call

from parameterized import parameterized
from aws_lambda_builders.actions import (
    CopySourceAction,
    CleanUpAction,
    MoveDependenciesAction,
    LinkSourceAction,
    LinkSinglePathAction,
)
from aws_lambda_builders.architecture import ARM64
from aws_lambda_builders.workflows.nodejs_npm.actions import NodejsNpmInstallAction, NodejsNpmCIAction
from aws_lambda_builders.workflows.nodejs_npm_esbuild import NodejsNpmEsbuildWorkflow
from aws_lambda_builders.workflows.nodejs_npm_esbuild.actions import EsbuildBundleAction
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import SubprocessEsbuild
from aws_lambda_builders.workflows.nodejs_npm_esbuild.exceptions import EsbuildExecutionError


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestNodejsNpmEsbuildWorkflow(TestCase):

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
        self.osutils.dirname.return_value = "source"
        self.osutils.is_windows.side_effect = [False]
        self.osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

    def test_workflow_sets_up_npm_actions_with_bundler_if_manifest_requests_it(self):
        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)
        self.osutils.file_exists.assert_has_calls(
            [call("source/package-lock.json"), call("source/npm-shrinkwrap.json")]
        )

    def test_sets_up_esbuild_search_path_from_npm_bin(self):
        self.popen.out = b"project/"

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.osutils.popen.assert_called_with(["npm", "root"], stdout="PIPE", stderr="PIPE", cwd="scratch_dir")
        esbuild = workflow.actions[2]._subprocess_esbuild

        self.assertIsInstance(esbuild, SubprocessEsbuild)
        self.assertEqual(esbuild.executable_search_paths, [str(Path("project/.bin"))])

    def test_sets_up_esbuild_search_path_with_workflow_executable_search_paths_after_npm_bin(self):
        self.popen.out = b"project"

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            executable_search_paths=["other/bin"],
            experimental_flags=[],
        )

        self.osutils.popen.assert_called_with(["npm", "root"], stdout="PIPE", stderr="PIPE", cwd="scratch_dir")
        esbuild = workflow.actions[2]._subprocess_esbuild
        self.assertIsInstance(esbuild, SubprocessEsbuild)
        self.assertEqual(esbuild.executable_search_paths, [str(Path("project/.bin")), "other/bin"])

    def test_workflow_uses_npm_ci_if_lockfile_exists(self):
        self.osutils.file_exists.side_effect = [True, True]

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            experimental_flags=[],
            options={"use_npm_ci": True},
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmCIAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)
        self.osutils.file_exists.assert_has_calls([call("source/package-lock.json")])

    def test_workflow_uses_npm_ci_if_shrinkwrap_exists(self):
        self.osutils.file_exists.side_effect = [True, False, True]

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            experimental_flags=[],
            options={"use_npm_ci": True},
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmCIAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)
        self.osutils.file_exists.assert_has_calls(
            [call("source/package-lock.json"), call("source/npm-shrinkwrap.json")]
        )

    def test_workflow_doesnt_use_npm_ci_no_options_config(self):
        self.osutils.file_exists.side_effect = [True, False, True]

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)
        self.osutils.file_exists.assert_has_calls(
            [call("source/package-lock.json"), call("source/npm-shrinkwrap.json")]
        )

    def test_must_validate_architecture(self):
        self.osutils.is_windows.side_effect = [False, False]
        self.osutils.popen.side_effect = [self.popen, self.popen]

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch",
            "source/manifest",
            options={"artifact_executable_name": "foo"},
            osutils=self.osutils,
            experimental_flags=[],
        )

        workflow_with_arm = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch",
            "source/manifest",
            architecture=ARM64,
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")

    def test_workflow_sets_up_esbuild_actions_with_download_dependencies_without_dependencies_dir(self):
        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)

    def test_workflow_sets_up_esbuild_actions_without_download_dependencies_with_dependencies_dir_combine_deps(self):
        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=False,
            combine_dependencies=True,
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], LinkSourceAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)

    def test_workflow_sets_up_esbuild_actions_without_download_dependencies_with_dependencies_dir_no_combine_deps(self):
        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=False,
            combine_dependencies=False,
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], LinkSourceAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)

    def test_workflow_sets_up_esbuild_actions_with_download_dependencies_and_dependencies_dir(self):
        self.osutils.file_exists.return_value = True

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)
        self.assertIsInstance(workflow.actions[3], CleanUpAction)
        self.assertIsInstance(workflow.actions[4], MoveDependenciesAction)

    def test_workflow_sets_up_esbuild_actions_with_download_dependencies_and_dependencies_dir_no_combine_deps(self):
        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)
        self.assertIsInstance(workflow.actions[3], CleanUpAction)
        self.assertIsInstance(workflow.actions[4], MoveDependenciesAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.workflow.NodejsNpmWorkflow")
    def test_workflow_uses_production_npm_version(self, get_workflow_mock):
        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            dependencies_dir=None,
            download_dependencies=True,
            combine_dependencies=False,
            osutils=self.osutils,
            experimental_flags=[],
        )

        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)

        get_workflow_mock.get_install_action.assert_called_with(
            source_dir="source",
            install_dir="scratch_dir",
            subprocess_npm=ANY,
            osutils=ANY,
            build_options=None,
            install_links=False,
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.workflow.NodejsNpmEsbuildWorkflow._get_esbuild_subprocess")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.workflow.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.workflow.OSUtils")
    def test_manifest_not_found(self, osutils_mock, subprocess_npm_mock, get_esbuild_subprocess_mock):
        osutils_mock.file_exists.return_value = False

        workflow = NodejsNpmEsbuildWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "source/manifest",
            osutils=osutils_mock,
        )

        self.assertEqual(len(workflow.actions), 1)
        self.assertIsInstance(workflow.actions[0], EsbuildBundleAction)

    def test_no_download_dependencies_and_no_dependencies_dir_fails(self):
        with self.assertRaises(EsbuildExecutionError):
            NodejsNpmEsbuildWorkflow(
                "source",
                "artifacts",
                "scratch_dir",
                "source/manifest",
                osutils=self.osutils,
                download_dependencies=False,
            )

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_build_in_source(self, install_links_mock):
        install_links_mock.return_value = True

        source_dir = "source"
        workflow = NodejsNpmEsbuildWorkflow(
            source_dir=source_dir,
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
        )

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], NodejsNpmInstallAction)
        self.assertEqual(workflow.actions[0].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[1], EsbuildBundleAction)
        self.assertEqual(workflow.actions[1]._working_directory, source_dir)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest(self):
        self.osutils.dirname.return_value = "not_source"

        workflow = NodejsNpmEsbuildWorkflow(
            source_dir="source",
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path="not_source/manifest",
            osutils=self.osutils,
        )

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], CopySourceAction)
        self.assertEquals(workflow.actions[1].source_dir, "not_source")
        self.assertEquals(workflow.actions[1].dest_dir, "scratch_dir")
        self.assertIsInstance(workflow.actions[2], NodejsNpmInstallAction)
        self.assertEquals(workflow.actions[2].install_dir, "scratch_dir")
        self.assertIsInstance(workflow.actions[3], EsbuildBundleAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest_and_build_in_source(
        self, install_links_mock
    ):
        install_links_mock.return_value = True

        self.osutils.dirname.return_value = "not_source"

        workflow = NodejsNpmEsbuildWorkflow(
            source_dir="source",
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path="not_source/manifest",
            osutils=self.osutils,
            build_in_source=True,
        )

        self.assertEqual(len(workflow.actions), 3)

        self.assertIsInstance(workflow.actions[0], NodejsNpmInstallAction)
        self.assertEquals(workflow.actions[0].install_dir, "not_source")
        self.assertIsInstance(workflow.actions[1], LinkSinglePathAction)
        self.assertEquals(workflow.actions[1]._source, os.path.join("not_source", "node_modules"))
        self.assertEquals(workflow.actions[1]._dest, os.path.join("source", "node_modules"))
        self.assertIsInstance(workflow.actions[2], EsbuildBundleAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.get_install_action")
    def test_workflow_revert_build_in_source(self, install_action_mock, install_links_mock):
        # fake having bad npm version
        install_links_mock.return_value = False

        source_dir = "source"
        artifacts_dir = "artifacts"
        scratch_dir = "scratch_dir"
        NodejsNpmEsbuildWorkflow(
            source_dir=source_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir=scratch_dir,
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=True,
            dependencies_dir="dep",
        )

        # expect no build in source and install dir is
        # scratch, not the source
        install_action_mock.assert_called_with(
            source_dir=source_dir,
            install_dir=scratch_dir,
            subprocess_npm=ANY,
            osutils=ANY,
            build_options=ANY,
            install_links=False,
        )

    @parameterized.expand(
        [
            (True, "source"),
            (False, "scratch_dir"),
        ]
    )
    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow.can_use_install_links")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.workflow.SubprocessNpm.run")
    def test_finds_correct_esbuild_binary(
        self, is_building_in_source, expected_dir, subprocess_run_mock, install_links_mock
    ):
        install_links_mock.return_value = True

        NodejsNpmEsbuildWorkflow(
            source_dir="source",
            artifacts_dir="artifacts",
            scratch_dir="scratch_dir",
            manifest_path="source/manifest",
            osutils=self.osutils,
            build_in_source=is_building_in_source,
        )

        subprocess_run_mock.assert_called_with(ANY, cwd=expected_dir)
