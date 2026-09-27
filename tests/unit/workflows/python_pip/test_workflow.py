from unittest import TestCase
from unittest.mock import patch, ANY, Mock

from parameterized import parameterized_class

from aws_lambda_builders.actions import CopySourceAction, CleanUpAction, LinkSourceAction
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.validator import RuntimeValidator
from aws_lambda_builders.workflows.python_pip.utils import OSUtils, EXPERIMENTAL_FLAG_BUILD_PERFORMANCE
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator
from aws_lambda_builders.workflows.python_pip.workflow import PythonPipBuildAction, PythonPipWorkflow


@parameterized_class(
    ("experimental_flags", "is_building_layer"),
    [
        ([], False),
        ([], True),
        ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE], False),
        ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE], True),
    ],
)
class TestPythonPipWorkflow(TestCase):
    experimental_flags = []
    is_building_layer = False

    @property
    def expects_linked_dependencies(self):
        """Dependencies are symlinked only when the build performance flag is on AND we are
        building a layer -- a function's artifacts are bind-mounted into the local invoke
        container, where symlinks pointing outside the mount dangle."""
        return bool(self.experimental_flags) and self.is_building_layer

    def setUp(self):
        self.osutils = OSUtils()
        self.osutils_mock = Mock(spec=self.osutils)
        self.osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )
        self.python_major_version = "3"
        self.python_minor_version = "9"
        self.language = "python"

    def test_workflow_sets_up_actions(self):
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_without_requirements(self):
        self.osutils_mock.file_exists.return_value = False
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )
        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_validator(self):
        for validator in self.workflow.get_validators():
            self.assertTrue(isinstance(validator, PythonRuntimeValidator))

    def test_workflow_validator_without_requirements_skips_python_validation(self):
        """When no requirements.txt exists, should use base RuntimeValidator (no Python binary check)."""
        self.osutils_mock.file_exists.return_value = False
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.12",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )
        validators = self.workflow.get_validators()
        self.assertEqual(len(validators), 1)
        self.assertIsInstance(validators[0], RuntimeValidator)
        self.assertNotIsInstance(validators[0], PythonRuntimeValidator)

    def test_workflow_validator_without_download_dependencies_skips_python_validation(self):
        """When download_dependencies=False, should use base RuntimeValidator (no Python binary check)."""
        self.osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.12",
            osutils=self.osutils_mock,
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
        )
        validators = self.workflow.get_validators()
        self.assertEqual(len(validators), 1)
        self.assertIsInstance(validators[0], RuntimeValidator)
        self.assertNotIsInstance(validators[0], PythonRuntimeValidator)

    def test_workflow_resolver(self):
        for resolver in self.workflow.get_resolvers():
            self.assertTrue(isinstance(resolver, PathResolver))
            self.assertTrue(
                resolver.executables,
                [
                    self.language,
                    f"{self.language}{self.python_major_version}.{self.python_minor_version}",
                    f"{self.language}{self.python_major_version}",
                ],
            )

    def test_workflow_sets_up_actions_without_download_dependencies_with_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
            is_building_layer=self.is_building_layer,
        )
        self.assertEqual(len(self.workflow.actions), 2)
        if self.expects_linked_dependencies:
            self.assertIsInstance(self.workflow.actions[0], LinkSourceAction)
        else:
            self.assertIsInstance(self.workflow.actions[0], CopySourceAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_with_download_dependencies_and_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=True,
            experimental_flags=self.experimental_flags,
            is_building_layer=self.is_building_layer,
        )
        self.assertEqual(len(self.workflow.actions), 4)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonPipBuildAction)
        if self.expects_linked_dependencies:
            self.assertIsInstance(self.workflow.actions[2], LinkSourceAction)
        else:
            self.assertIsInstance(self.workflow.actions[2], CopySourceAction)
            # check copying dependencies does not have any exclude
            self.assertEqual(self.workflow.actions[2].excludes, [])
        self.assertIsInstance(self.workflow.actions[3], CopySourceAction)

    def test_workflow_sets_up_actions_without_download_dependencies_without_dependencies_dir(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir=None,
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
        )
        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_sets_up_actions_without_combine_dependencies(self):
        osutils_mock = Mock(spec=self.osutils)
        osutils_mock.file_exists.return_value = True
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=osutils_mock,
            dependencies_dir="dep",
            download_dependencies=True,
            combine_dependencies=False,
            experimental_flags=self.experimental_flags,
        )
        self.assertEqual(len(self.workflow.actions), 3)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopySourceAction)

    def test_layer_links_dependencies_while_function_copies_them(self):
        """The layer/function distinction is the whole reason linking is safe at all, so assert the
        contrast on inputs that are otherwise identical -- otherwise a future change that drops
        is_building_layer still passes every other test in this class."""

        def actions_for(is_building_layer):
            osutils_mock = Mock(spec=self.osutils)
            osutils_mock.file_exists.return_value = True
            return PythonPipWorkflow(
                "source",
                "artifacts",
                "scratch_dir",
                "manifest",
                runtime="python3.9",
                osutils=osutils_mock,
                dependencies_dir="dep",
                download_dependencies=True,
                experimental_flags=[EXPERIMENTAL_FLAG_BUILD_PERFORMANCE],
                is_building_layer=is_building_layer,
            ).actions

        self.assertIsInstance(actions_for(is_building_layer=True)[2], LinkSourceAction)
        self.assertIsInstance(actions_for(is_building_layer=False)[2], CopySourceAction)

    @patch("aws_lambda_builders.workflows.python_pip.workflow.PythonPipBuildAction")
    def test_must_build_with_architecture(self, PythonPipBuildActionMock):
        self.workflow = PythonPipWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            architecture="ARM64",
            osutils=self.osutils_mock,
        )
        PythonPipBuildActionMock.assert_called_with(
            "artifacts",
            "scratch_dir",
            "manifest",
            "python3.9",
            None,
            binaries=ANY,
            architecture="ARM64",
        )
        self.assertEqual(2, len(self.workflow.actions))
