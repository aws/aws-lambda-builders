import os
from unittest import TestCase
from unittest.mock import patch, call, Mock

from parameterized import parameterized

from aws_lambda_builders.actions import (
    CopySourceAction,
    CleanUpAction,
    CopyDependenciesAction,
    LinkSinglePathAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.architecture import ARM64
from aws_lambda_builders.workflows.nodejs_npm.exceptions import OldNpmVersionError
from aws_lambda_builders.workflows.nodejs_npm.workflow import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmCIAction,
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

        self.assertEqual(len(workflow.actions), 6)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmLockFileCleanUpAction)

    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest(self):
        self.osutils.dirname.return_value = "not_source"
        self.osutils.file_exists.return_value = True

        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "not_source/manifest", osutils=self.osutils)

        self.assertEqual(len(workflow.actions), 7)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertEqual(workflow.actions[3].source_dir, "source")
        self.assertEqual(workflow.actions[3].dest_dir, "artifacts")
        self.assertIsInstance(workflow.actions[4], NodejsNpmInstallAction)
        self.assertEqual(workflow.actions[4].install_dir, "artifacts")
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmLockFileCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow._can_use_install_links")
    def test_workflow_sets_up_npm_actions_with_download_dependencies_without_dependencies_dir_external_manifest_and_build_in_source(
        self, can_use_links_mock
    ):
        can_use_links_mock.return_value = True

        self.osutils.dirname.return_value = "not_source"
        self.osutils.file_exists.return_value = True

        self.osutils.file_exists.side_effect = [True, False, False]

        workflow = NodejsNpmWorkflow(
            "source", "artifacts", "scratch_dir", "not_source/manifest", osutils=self.osutils, build_in_source=True
        )

        self.assertEqual(len(workflow.actions), 8)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], CopySourceAction)
        self.assertEqual(workflow.actions[3].source_dir, "source")
        self.assertEqual(workflow.actions[3].dest_dir, "artifacts")
        self.assertIsInstance(workflow.actions[4], NodejsNpmInstallAction)
        self.assertEqual(workflow.actions[4].install_dir, "not_source")
        self.assertIsInstance(workflow.actions[5], LinkSinglePathAction)
        self.assertEqual(workflow.actions[5]._source, os.path.join("not_source", "node_modules"))
        self.assertEqual(workflow.actions[5]._dest, os.path.join("source", "node_modules"))
        self.assertIsInstance(workflow.actions[6], LinkSinglePathAction)
        self.assertEqual(workflow.actions[6]._source, os.path.join("source", "node_modules"))
        self.assertEqual(workflow.actions[6]._dest, os.path.join("artifacts", "node_modules"))
        self.assertIsInstance(workflow.actions[7], NodejsNpmrcCleanUpAction)

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

        self.assertEqual(len(workflow.actions), 6)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmLockFileCleanUpAction)

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

        self.assertEqual(len(workflow.actions), 9)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], CleanUpAction)
        self.assertIsInstance(workflow.actions[5], CopyDependenciesAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmLockFileCleanUpAction)
        self.assertIsInstance(workflow.actions[8], NodejsNpmLockFileCleanUpAction)

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

        self.assertEqual(len(workflow.actions), 9)

        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertIsInstance(workflow.actions[4], CleanUpAction)
        self.assertIsInstance(workflow.actions[5], MoveDependenciesAction)
        self.assertIsInstance(workflow.actions[6], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmLockFileCleanUpAction)
        self.assertIsInstance(workflow.actions[8], NodejsNpmLockFileCleanUpAction)

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

        self.assertEqual(len(workflow.actions), 6)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmCIAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmLockFileCleanUpAction)
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

        self.assertEqual(len(workflow.actions), 6)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmCIAction)
        self.assertIsInstance(workflow.actions[4], NodejsNpmrcCleanUpAction)
        self.assertIsInstance(workflow.actions[5], NodejsNpmLockFileCleanUpAction)
        self.osutils.file_exists.assert_has_calls([call("source/package-lock.json")])

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow._can_use_install_links")
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

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow._can_use_install_links")
    def test_build_in_source_with_download_dependencies(self, can_use_links_mock):
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
        )

        self.assertEqual(len(workflow.actions), 6)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertEqual(workflow.actions[3].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[4], LinkSinglePathAction)
        self.assertEqual(workflow.actions[4]._source, os.path.join(source_dir, "node_modules"))
        self.assertEqual(workflow.actions[4]._dest, os.path.join(artifacts_dir, "node_modules"))
        self.assertIsInstance(workflow.actions[5], NodejsNpmrcCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow._can_use_install_links")
    def test_build_in_source_with_download_dependencies_and_dependencies_dir(self, can_use_links_mock):
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
        )

        self.assertEqual(len(workflow.actions), 8)
        self.assertIsInstance(workflow.actions[0], NodejsNpmPackAction)
        self.assertIsInstance(workflow.actions[1], NodejsNpmrcAndLockfileCopyAction)
        self.assertIsInstance(workflow.actions[2], CopySourceAction)
        self.assertIsInstance(workflow.actions[3], NodejsNpmInstallAction)
        self.assertEqual(workflow.actions[3].install_dir, source_dir)
        self.assertIsInstance(workflow.actions[4], LinkSinglePathAction)
        self.assertEqual(workflow.actions[4]._source, os.path.join(source_dir, "node_modules"))
        self.assertEqual(workflow.actions[4]._dest, os.path.join(artifacts_dir, "node_modules"))
        self.assertIsInstance(workflow.actions[5], CleanUpAction)
        self.assertIsInstance(workflow.actions[6], CopyDependenciesAction)
        self.assertIsInstance(workflow.actions[7], NodejsNpmrcCleanUpAction)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow._can_use_install_links")
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
            ("8.8", False),
            ("foo", False),
            ("", False),
        ]
    )
    def test_npm_version_validation(self, returned_npm_version, expected_result):
        workflow = NodejsNpmWorkflow("source", "artifacts", "scratch_dir", "source/manifest")

        npm_subprocess = Mock()
        npm_subprocess.run = Mock(return_value=returned_npm_version)

        result = workflow._can_use_install_links(npm_subprocess)

        self.assertEqual(result, expected_result)

    @patch("aws_lambda_builders.workflows.nodejs_npm.workflow.NodejsNpmWorkflow._can_use_install_links")
    def test_build_in_source_old_npm_raises_exception(self, install_links_mock):
        install_links_mock.return_value = False

        with self.assertRaises(OldNpmVersionError):
            NodejsNpmWorkflow(
                "source", "artifacts", "scratch_dir", "source/manifest", osutils=self.osutils, build_in_source=True
            )
