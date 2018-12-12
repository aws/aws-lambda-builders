from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.ruby_bundler.workflow import RubyBundlerWorkflow
from aws_lambda_builders.workflows.ruby_bundler.actions import RubyBundlerInstallAction, RubyBundlerVendorAction


class TestRubyBundlerWorkflow(TestCase):
    """
    the workflow requires an external utility (bundler) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_bundler_actions(self):
        workflow = RubyBundlerWorkflow("source", "artifacts", "scratch_dir", "manifest")
        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], RubyBundlerInstallAction)
        self.assertIsInstance(workflow.actions[2], RubyBundlerVendorAction)
