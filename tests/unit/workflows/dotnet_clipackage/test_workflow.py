from unittest import TestCase

from aws_lambda_builders.workflows.dotnet_clipackage.workflow import DotnetCliPackageWorkflow
from aws_lambda_builders.workflows.dotnet_clipackage.actions import GlobalToolInstallAction, RunPackageAction


class TestDotnetCliPackageWorkflow(TestCase):

    def test_actions(self):
        workflow = DotnetCliPackageWorkflow("source_dir", "artifacts_dir", "scratch_dir", "manifest_path")
        self.assertEqual(workflow.actions.__len__(), 2)

        self.assertIsInstance(workflow.actions[0], GlobalToolInstallAction)
        self.assertIsInstance(workflow.actions[1], RunPackageAction)
