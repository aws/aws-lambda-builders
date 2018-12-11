from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.ruby.actions import RubyBundlerInstallAction, RubyBundlerVendorAction
from aws_lambda_builders.workflows.ruby.bundler import BundlerExecutionError


class TestRubyBundlerInstallAction(TestCase):
    @patch("aws_lambda_builders.workflows.ruby.bundler.SubprocessBundler")
    def test_runs_bundle_install(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        action = RubyBundlerInstallAction("source_dir",
                                          subprocess_bundler=subprocess_bundler)
        action.execute()
        subprocess_bundler.run.assert_called_with(['install'], cwd="source_dir")

    @patch("aws_lambda_builders.workflows.ruby.bundler.SubprocessBundler")
    def test_raises_action_failed_on_failure(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        builder_instance = SubprocessBundlerMock.return_value
        builder_instance.run.side_effect = BundlerExecutionError(message="Fail")
        action = RubyBundlerInstallAction("source_dir",
                                          subprocess_bundler=subprocess_bundler)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "Bundler Failed: Fail")

class TestRubyBundlerVendorAction(TestCase):
    @patch("aws_lambda_builders.workflows.ruby.bundler.SubprocessBundler")
    def test_runs_bundle_install_deployment(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        action = RubyBundlerVendorAction("source_dir",
                                          subprocess_bundler=subprocess_bundler)
        action.execute()
        subprocess_bundler.run.assert_called_with(['install', '--deployment'], cwd="source_dir")
    
    @patch("aws_lambda_builders.workflows.ruby.bundler.SubprocessBundler")
    def test_raises_action_failed_on_failure(self, SubprocessBundlerMock):
        subprocess_bundler = SubprocessBundlerMock.return_value
        builder_instance = SubprocessBundlerMock.return_value
        builder_instance.run.side_effect = BundlerExecutionError(message="Fail")
        action = RubyBundlerVendorAction("source_dir",
                                          subprocess_bundler=subprocess_bundler)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "Bundler Failed: Fail")
