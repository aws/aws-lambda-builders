import sys

from unittest import TestCase
from mock import patch, Mock

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.binary_path import BinaryPath

from aws_lambda_builders.workflows.python_pip.actions import PythonPipBuildAction
from aws_lambda_builders.workflows.python_pip.exceptions import MissingPipError
from aws_lambda_builders.workflows.python_pip.packager import PackagerError


class TestPythonPipBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    def test_action_must_call_builder(self, PythonPipDependencyBuilderMock):
        builder_instance = PythonPipDependencyBuilderMock.return_value

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
        )
        action.execute()

        builder_instance.build_dependencies.assert_called_with(
            artifacts_dir_path="artifacts", scratch_dir_path="scratch_dir", requirements_path="manifest"
        )

    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    def test_must_raise_exception_on_failure(self, PythonPipDependencyBuilderMock):
        builder_instance = PythonPipDependencyBuilderMock.return_value
        builder_instance.build_dependencies.side_effect = PackagerError()

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
        )

        with self.assertRaises(ActionFailedError):
            action.execute()

    @patch("aws_lambda_builders.workflows.python_pip.actions.SubprocessPip")
    def test_must_raise_exception_on_pip_failure(self, PythonSubProcessPipMock):
        PythonSubProcessPipMock.side_effect = MissingPipError(python_path="mockpath")

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
        )

        with self.assertRaises(ActionFailedError):
            action.execute()
