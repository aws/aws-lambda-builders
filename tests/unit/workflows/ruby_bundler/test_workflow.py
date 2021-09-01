from unittest import TestCase

from aws_lambda_builders.actions import CopySourceAction, CopyDependenciesAction
from aws_lambda_builders.workflows.ruby_bundler.workflow import RubyBundlerWorkflow
from aws_lambda_builders.workflows.ruby_bundler.actions import RubyBundlerInstallAction, RubyBundlerVendorAction


class TestRubyBundlerWorkflow(TestCase):
    """
    the workflow requires an external utility (bundler) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_bundler_actions_with_download_dependencies_without_dependencies_dir(self):
        workflow = RubyBundlerWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", download_dependencies=False
        )
        self.assertEqual(len(workflow.actions), 3)
        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], RubyBundlerInstallAction)
        self.assertIsInstance(workflow.actions[2], RubyBundlerVendorAction)

    def test_workflow_sets_up_npm_actions_without_download_dependencies(self):
        workflow = RubyBundlerWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", download_dependencies=False
        )

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_bundler_actions_with_download_dependencies_without_dependencies_dir(self):
        workflow = RubyBundlerWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", download_dependencies=True
        )

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)
        self.assertIsInstance(workflow.actions[1], RubyBundlerInstallAction)
        self.assertIsInstance(workflow.actions[2], RubyBundlerVendorAction)
        self.assertIsInstance(workflow.actions[3], CopyDependenciesAction)
