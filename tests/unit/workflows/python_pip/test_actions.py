import sys

from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock, ANY

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.binary_path import BinaryPath

from aws_lambda_builders.workflows.python_pip.actions import PythonPipBuildAction
from aws_lambda_builders.workflows.python_pip.exceptions import MissingPipError
from aws_lambda_builders.workflows.python_pip.packager import PackagerError


class TestPythonPipBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    @patch("aws_lambda_builders.workflows.python_pip.actions.DependencyBuilder")
    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipBuildAction._find_runtime_with_pip")
    def test_action_must_call_builder(self, find_runtime_mock, dependency_builder_mock, pip_dependency_builder_mock):
        builder_instance = pip_dependency_builder_mock.return_value
        find_runtime_mock.return_value = (Mock(), Mock())

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            None,
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
        )
        action.execute()

        dependency_builder_mock.assert_called_with(osutils=ANY, pip_runner=ANY, runtime="runtime", architecture=X86_64)

        builder_instance.build_dependencies.assert_called_with(
            artifacts_dir_path="artifacts", scratch_dir_path="scratch_dir", requirements_path="manifest"
        )

    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    @patch("aws_lambda_builders.workflows.python_pip.actions.DependencyBuilder")
    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipBuildAction._find_runtime_with_pip")
    def test_action_must_call_builder_with_architecture(
        self, find_runtime_mock, dependency_builder_mock, pip_dependency_builder_mock
    ):
        builder_instance = pip_dependency_builder_mock.return_value
        find_runtime_mock.return_value = (Mock(), Mock())

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            None,
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
            ARM64,
        )
        action.execute()

        dependency_builder_mock.assert_called_with(osutils=ANY, pip_runner=ANY, runtime="runtime", architecture=ARM64)

        builder_instance.build_dependencies.assert_called_with(
            artifacts_dir_path="artifacts", scratch_dir_path="scratch_dir", requirements_path="manifest"
        )

    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipBuildAction._find_runtime_with_pip")
    def test_must_raise_exception_on_failure(self, find_runtime_mock, pip_dependency_builder_mock):
        builder_instance = pip_dependency_builder_mock.return_value
        builder_instance.build_dependencies.side_effect = PackagerError()
        find_runtime_mock.return_value = (Mock(), Mock())

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            None,
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
        )

        with self.assertRaises(ActionFailedError):
            action.execute()

    # @patch("aws_lambda_builders.workflows.python_pip.actions.SubprocessPip")
    # @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipBuildAction._find_runtime_with_pip")
    # def test_must_raise_exception_on_pip_failure(self, find_runtime_mock, pip_sub_process_mock):
    #     pip_sub_process_mock.side_effect = MissingPipError(python_path="mockpath")
    #     find_runtime_mock.return_value = (Mock(), Mock())

    #     action = PythonPipBuildAction(
    #         "artifacts",
    #         "scratch_dir",
    #         "manifest",
    #         "runtime",
    #         None,
    #         {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
    #     )

    #     with self.assertRaises(ActionFailedError):
    #         action.execute()

    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipDependencyBuilder")
    @patch("aws_lambda_builders.workflows.python_pip.actions.PythonPipBuildAction._find_runtime_with_pip")
    def test_action_must_call_builder_with_dependencies_dir(self, find_runtime_mock, pip_dependency_builder_mock):
        builder_instance = pip_dependency_builder_mock.return_value
        find_runtime_mock.return_value = (Mock(), Mock())

        action = PythonPipBuildAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            "runtime",
            "dependencies_dir",
            {"python": BinaryPath(resolver=Mock(), validator=Mock(), binary="python", binary_path=sys.executable)},
        )
        action.execute()

        builder_instance.build_dependencies.assert_called_with(
            artifacts_dir_path="dependencies_dir", scratch_dir_path="scratch_dir", requirements_path="manifest"
        )

    def test_find_runtime_missing_binary_object(self):
        mock_binaries = {}

        with self.assertRaises(ActionFailedError) as ex:
            PythonPipBuildAction(Mock(), Mock(), Mock(), Mock(), Mock(), mock_binaries)._find_runtime_with_pip()

            self.assertEqual(str(ex.exception), "Failed to fetch Python binaries from the PATH.")

    def test_find_runtime_empty_exec_paths(self):
        mock_resolver = Mock()
        mock_resolver.resolver = Mock()
        mock_resolver.resolver.exec_paths = {}

        mock_binaries = Mock()
        mock_binaries.get = Mock(return_value=mock_resolver)

        with self.assertRaises(ActionFailedError) as ex:
            PythonPipBuildAction(Mock(), Mock(), Mock(), Mock(), Mock(), mock_binaries)._find_runtime_with_pip()

            self.assertEqual(str(ex.exception), "Failed to fetch Python binaries from the PATH.")

    def test_find_runtime_found_pip(self):
        pass

    def test_find_runtime_no_matches(self):
        pass
