from unittest import TestCase

from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflows.rust_cargo.workflow import RustCargoWorkflow
from aws_lambda_builders.workflows.rust_cargo.actions import BuildAction, CopyAndRenameAction


class TestRustCargoWorkflow(TestCase):
    """
    Validate workflow wiring
    """

    def test_workflow_sets_up_builder_actions(self):
        workflow = RustCargoWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="provided")
        self.assertEqual(len(workflow.actions), 2)
        self.assertIsInstance(workflow.actions[0], BuildAction)
        self.assertIsInstance(workflow.actions[1], CopyAndRenameAction)

    def test_workflow_configures_path_resolver_for_cargo(self):
        workflow = RustCargoWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="provided")
        resolvers = workflow.get_resolvers()
        self.assertEqual(len(resolvers), 1)
        resolver = resolvers[0]
        self.assertIsInstance(resolver, PathResolver)
        self.assertEqual(resolver.binary, "cargo")
        self.assertEqual(resolver.runtime, "provided")
