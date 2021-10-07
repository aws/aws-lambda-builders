from unittest import TestCase

from aws_lambda_builders.workflows.go_modules.workflow import GoModulesWorkflow
from aws_lambda_builders.workflows.go_modules.actions import GoModulesBuildAction
from aws_lambda_builders.architecture import X86_64, ARM64


class TestGoModulesWorkflow(TestCase):
    """
    the workflow requires an external utility (builder) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_builder_actions(self):
        workflow = GoModulesWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="go1.x",
            options={"artifact_executable_name": "main"},
        )

        self.assertEqual(len(workflow.actions), 1)
        self.assertIsInstance(workflow.actions[0], GoModulesBuildAction)

    def test_must_validate_architecture(self):
        workflow = GoModulesWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
        )
        workflow_with_arm = GoModulesWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
            architecture=ARM64,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")
