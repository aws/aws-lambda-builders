from unittest import TestCase

from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflows.rust_cargo.workflow import RustCargoWorkflow
from aws_lambda_builders.workflows.rust_cargo.actions import RustBuildAction, RustCopyAndRenameAction


class TestRustCargoWorkflow(TestCase):
    """
    Validate workflow wiring
    """

    def test_workflow_sets_up_builder_actions(self):
        workflow = RustCargoWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="provided")
        self.assertEqual(len(workflow.actions), 2)
        self.assertIsInstance(workflow.actions[0], RustBuildAction)
        self.assertIsInstance(workflow.actions[1], RustCopyAndRenameAction)

    def test_workflow_configures_path_resolver_for_cargo(self):
        workflow = RustCargoWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="provided")
        resolvers = workflow.get_resolvers()
        self.assertEqual(len(resolvers), 2)
        resolver = resolvers[0]
        self.assertIsInstance(resolver, PathResolver)
        self.assertEqual(resolver.binary, "cargo")
        self.assertEqual(resolver.runtime, "provided")
        resolver = resolvers[1]
        self.assertIsInstance(resolver, PathResolver)
        self.assertEqual(resolver.binary, "cargo-lambda")
        self.assertEqual(resolver.runtime, "provided")
