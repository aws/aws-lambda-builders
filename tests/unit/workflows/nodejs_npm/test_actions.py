from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.actions import \
    NodejsNpmPackAction, NodejsNpmInstallAction, NodejsNpmrcCopyAction, NodejsNpmrcCleanUpAction
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError


class TestNodejsNpmPackAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmPackAction("artifacts", "scratch_dir",
                                     "manifest",
                                     osutils=osutils,
                                     subprocess_npm=subprocess_npm)

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        subprocess_npm.run.return_value = 'package.tar'

        action.execute()

        subprocess_npm.run.assert_called_with(['pack', '-q', 'file:/abs:/dir:manifest'], cwd='scratch_dir')
        osutils.extract_tarfile.assert_called_with('scratch_dir/package.tar', 'artifacts')

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmPackAction("artifacts", "scratch_dir",
                                     "manifest",
                                     osutils=osutils, subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmInstallAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("artifacts",
                                        subprocess_npm=subprocess_npm)

        action.execute()

        expected_args = ['install', '-q', '--no-audit', '--no-save', '--production']

        subprocess_npm.run.assert_called_with(expected_args, cwd='artifacts')

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmInstallAction("artifacts",
                                        subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmrcCopyAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_copies_npmrc_into_a_project(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCopyAction("artifacts",
                                       "source",
                                       osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.file_exists.assert_called_with("source/.npmrc")
        osutils.copy_file.assert_called_with("source/.npmrc", "artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_copying_npmrc_into_a_project_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCopyAction("artifacts",
                                       "source",
                                       osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.file_exists.assert_called_with("source/.npmrc")
        osutils.copy_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_copying_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.copy_file.side_effect = OSError()

        action = NodejsNpmrcCopyAction("artifacts",
                                       "source",
                                       osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmrcCleanUpAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_npmrc_if_npmrc_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction(
                                     "artifacts",
                                     osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/.npmrc")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_npmrc_removal_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction(
                                     "artifacts",
                                     osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()
