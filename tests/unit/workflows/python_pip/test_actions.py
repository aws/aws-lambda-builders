
from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError

from aws_lambda_builders.workflows.python_pip.actions import PythonPipBuildAction
from aws_lambda_builders.workflows.python_pip.packager import PackagerError


class TestPythonPipBuildAction(TestCase):

    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    def test_action_must_call_builder(self, PythonPipDependencyBuilderMock):
        builder_instance = PythonPipDependencyBuilderMock.return_value

        action = PythonPipBuildAction("artifacts", "manifest", "runtime")
        action.execute()

        builder_instance.build_dependencies.assert_called_with("artifacts", "manifest", "runtime")

    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    def test_must_raise_exception_on_failure(self, PythonPipDependencyBuilderMock):
        builder_instance = PythonPipDependencyBuilderMock.return_value
        builder_instance.build_dependencies.side_effect = PackagerError()

        action = PythonPipBuildAction("artifacts", "manifest", "runtime")

        with self.assertRaises(ActionFailedError):
            action.execute()
