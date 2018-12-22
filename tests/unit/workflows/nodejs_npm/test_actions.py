from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.actions import \
    NodejsNpmPackAction, NodejsNpmInstallAction, NodejsNpmScriptAction
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


class TestNodejsNpmScriptAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_does_not_execute_script_if_no_scripts(self, SubprocessNpmMock, OSUtilMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmScriptAction("workdir",
                                       "manifest_path",
                                       "script_name",
                                       subprocess_npm=subprocess_npm,
                                       osutils=osutils)

        osutils.get_text_contents.side_effect = ['{"version":"1.0.0"}']

        action.execute()

        subprocess_npm.run.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_does_not_execute_script_if_requested_script_not_defined(self, SubprocessNpmMock, OSUtilMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmScriptAction("workdir",
                                       "manifest_path",
                                       "script_name",
                                       subprocess_npm=subprocess_npm,
                                       osutils=osutils)

        osutils.get_text_contents.side_effect = ['{"version":"1.0.0","scripts":{"not_script_name":"something"}}']

        action.execute()

        subprocess_npm.run.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_executes_script_if_requested_script_is_defined(self, SubprocessNpmMock, OSUtilMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmScriptAction("workdir",
                                       "manifest_path",
                                       "script_name",
                                       subprocess_npm=subprocess_npm,
                                       osutils=osutils)

        osutils.get_text_contents.side_effect = ['{"version":"1.0.0","scripts":{"script_name":"something"}}']

        action.execute()

        subprocess_npm.run.assert_called_with(['run', 'script_name'], cwd='workdir')

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_reads_manifest_path_to_get_json(self, SubprocessNpmMock, OSUtilMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmScriptAction("workdir",
                                       "manifest_path",
                                       "script_name",
                                       subprocess_npm=subprocess_npm,
                                       osutils=osutils)

        osutils.get_text_contents.side_effect = ['{}']

        action.execute()

        osutils.get_text_contents.assert_called_with('manifest_path')

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock, OSUtilMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        subprocess_npm.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmScriptAction("workdir",
                                       "manifest_path",
                                       "script_name",
                                       subprocess_npm=subprocess_npm,
                                       osutils=osutils)

        osutils.get_text_contents.side_effect = ['{"scripts":{"script_name":"script_name"}}']

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_if_manifest_not_json(self, SubprocessNpmMock, OSUtilMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        osutils.get_text_contents.side_effect = ["test=True"]

        action = NodejsNpmScriptAction("workdir",
                                       "manifest_path",
                                       "script_name",
                                       subprocess_npm=subprocess_npm,
                                       osutils=osutils)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertIn("manifest_path is not valid json:", str(raised.exception))
