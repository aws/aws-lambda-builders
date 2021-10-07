from unittest import TestCase

from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.workflows.dotnet_clipackage.workflow import DotnetCliPackageWorkflow
from aws_lambda_builders.workflows.dotnet_clipackage.actions import GlobalToolInstallAction, RunPackageAction


class TestDotnetCliPackageWorkflow(TestCase):
    def test_actions(self):
        workflow = DotnetCliPackageWorkflow("source_dir", "artifacts_dir", "scratch_dir", "manifest_path")
        self.assertEqual(workflow.actions.__len__(), 2)

        self.assertIsInstance(workflow.actions[0], GlobalToolInstallAction)
        self.assertIsInstance(workflow.actions[1], RunPackageAction)

    def test_must_validate_architecture(self):
        workflow = DotnetCliPackageWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
        )
        workflow_with_arm = DotnetCliPackageWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
            architecture=ARM64,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")
