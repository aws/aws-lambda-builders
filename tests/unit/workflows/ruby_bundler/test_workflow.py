from unittest import TestCase

import mock

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.ruby_bundler.utils import OSUtils
from aws_lambda_builders.workflows.ruby_bundler.workflow import RubyBundlerWorkflow
from aws_lambda_builders.workflows.ruby_bundler.actions import RubyBundlerInstallAction, RubyBundlerVendorAction


class TestRubyBundlerWorkflow(TestCase):
    """
    the workflow requires an external utility (bundler) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def setUp(self):
        self.osutils = OSUtils()

    def test_workflow_sets_up_bundler_actions(self):
        osutils_mock = mock.Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        workflow = RubyBundlerWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=osutils_mock)
        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], RubyBundlerInstallAction)
        self.assertIsInstance(workflow.actions[2], RubyBundlerVendorAction)

    def test_workflow_sets_up_bundler_actions_without_gemfile(self):
        osutils_mock = mock.Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = False
        workflow = RubyBundlerWorkflow("source", "artifacts", "scratch_dir", "manifest", osutils=osutils_mock)
        self.assertEqual(len(workflow.actions), 1)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
