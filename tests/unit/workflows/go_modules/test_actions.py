from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.go_modules.actions import GoModulesBuildAction
from aws_lambda_builders.workflows.go_modules.builder import BuilderError


class TestGoModulesBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.go_modules.builder.GoModulesBuilder")
    def test_runs_bundle_install(self, BuilderMock):
        builder = BuilderMock.return_value
        action = GoModulesBuildAction("source_dir", "output_path", builder)
        action.execute()
        builder.build.assert_called_with("source_dir", "output_path")

    @patch("aws_lambda_builders.workflows.go_modules.builder.GoModulesBuilder")
    def test_raises_action_failed_on_failure(self, BuilderMock):
        builder = BuilderMock.return_value
        builder.build.side_effect = BuilderError(message="Fail")
        action = GoModulesBuildAction("source_dir", "output_path", builder)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()
        self.assertEqual(raised.exception.args[0], "Builder Failed: Fail")
