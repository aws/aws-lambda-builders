from unittest import TestCase

from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflows.rust_cargo.workflow import RustCargoLambdaWorkflow
from aws_lambda_builders.workflows.rust_cargo.actions import RustCargoLambdaBuildAction, RustCopyAndRenameAction
from aws_lambda_builders.workflows.rust_cargo.feature_flag import EXPERIMENTAL_FLAG_CARGO_LAMBDA


class TestRustCargoLambdaWorkflow(TestCase):
    """
    Validate workflow wiring
    """

    def test_workflow_sets_up_builder_actions(self):
        workflow = RustCargoLambdaWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="provided",
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )
        self.assertEqual(len(workflow.actions), 2)
        self.assertIsInstance(workflow.actions[0], RustCargoLambdaBuildAction)
        self.assertIsInstance(workflow.actions[1], RustCopyAndRenameAction)

    def test_workflow_configures_path_resolver_for_cargo(self):
        workflow = RustCargoLambdaWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="provided",
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )
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
