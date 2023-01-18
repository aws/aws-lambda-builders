import os
import sys
from unittest import TestCase
from parameterized import parameterized

from mock import Mock, MagicMock, call

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.validator import RuntimeValidator
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability
from aws_lambda_builders.registry import get_workflow, DEFAULT_REGISTRY
from aws_lambda_builders.exceptions import (
    WorkflowFailedError,
    WorkflowUnknownError,
    MisMatchRuntimeError,
    UnsupportedRuntimeError,
    UnsupportedArchitectureError,
)
from aws_lambda_builders.actions import ActionFailedError


class TestRegisteringWorkflows(TestCase):

    CAPABILITY1 = Capability(language="test", dependency_manager="testframework", application_framework="appframework")

    CAPABILITY2 = Capability(
        language="test2", dependency_manager="testframework2", application_framework="appframework2"
    )

    def tearDown(self):
        DEFAULT_REGISTRY.clear()

    def test_must_register_one_workflow(self):

        # Just loading the classes will register them to default registry
        class TestWorkflow(BaseWorkflow):
            NAME = "TestWorkflow"
            CAPABILITY = self.CAPABILITY1
            DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
            BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        result_cls = get_workflow(self.CAPABILITY1)
        self.assertEqual(len(DEFAULT_REGISTRY), 1)
        self.assertEqual(result_cls, TestWorkflow)

    def test_must_register_two_workflows(self):
        class TestWorkflow1(BaseWorkflow):
            NAME = "TestWorkflow"
            CAPABILITY = self.CAPABILITY1
            DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
            BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        class TestWorkflow2(BaseWorkflow):
            NAME = "TestWorkflow2"
            CAPABILITY = self.CAPABILITY2
            DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
            BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        self.assertEqual(len(DEFAULT_REGISTRY), 2)
        self.assertEqual(get_workflow(self.CAPABILITY1), TestWorkflow1)
        self.assertEqual(get_workflow(self.CAPABILITY2), TestWorkflow2)

    def test_must_fail_if_name_not_present(self):

        with self.assertRaises(ValueError) as ctx:

            class TestWorkflow1(BaseWorkflow):
                CAPABILITY = self.CAPABILITY1
                DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
                BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        self.assertEqual(len(DEFAULT_REGISTRY), 0)
        self.assertEqual(str(ctx.exception), "Workflow must provide a valid name")

    def test_must_fail_if_capabilities_not_present(self):

        with self.assertRaises(ValueError) as ctx:

            class TestWorkflow1(BaseWorkflow):
                NAME = "somename"
                DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
                BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        self.assertEqual(len(DEFAULT_REGISTRY), 0)
        self.assertEqual(str(ctx.exception), "Workflow 'somename' must register valid capabilities")

    def test_must_fail_if_capabilities_is_wrong_type(self):

        with self.assertRaises(ValueError) as ctx:

            class TestWorkflow1(BaseWorkflow):
                NAME = "somename"
                CAPABILITY = "wrong data type"
                DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
                BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        self.assertEqual(len(DEFAULT_REGISTRY), 0)
        self.assertEqual(str(ctx.exception), "Workflow 'somename' must register valid capabilities")

    @parameterized.expand(
        [
            (None,),  # support not defined
            (False,),  # support not instance of enum
        ]
    )
    def test_must_fail_if_build_in_source_support_invalid(self, build_in_source_support):

        with self.assertRaises(ValueError) as ctx:

            class TestWorkflow1(BaseWorkflow):
                NAME = "somename"
                CAPABILITY = self.CAPABILITY1
                DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
                BUILD_IN_SOURCE_SUPPORT = build_in_source_support

        self.assertEqual(len(DEFAULT_REGISTRY), 0)

    @parameterized.expand(
        [
            (None,),  # default build dir not defined
            ("some_dir",),  # default build dir not instance of enum
        ]
    )
    def test_must_fail_if_default_build_dir_invalid(self, default_build_dir):

        with self.assertRaises(ValueError) as ctx:

            class TestWorkflow1(BaseWorkflow):
                NAME = "somename"
                CAPABILITY = self.CAPABILITY1
                DEFAULT_BUILD_DIR = default_build_dir
                BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.NOT_SUPPORTED

        self.assertEqual(len(DEFAULT_REGISTRY), 0)


class TestBaseWorkflow_init(TestCase):
    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(
            language="test", dependency_manager="testframework", application_framework="appframework"
        )
        DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
        BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def test_must_initialize_variables(self):
        self.work = self.MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[str(sys.executable)],
            optimizations={"a": "b"},
            options={"c": "d"},
        )

        self.assertEqual(self.work.source_dir, "source_dir")
        self.assertEqual(self.work.artifacts_dir, "artifacts_dir")
        self.assertEqual(self.work.scratch_dir, "scratch_dir")
        self.assertEqual(self.work.manifest_path, "manifest_path")
        self.assertEqual(self.work.runtime, "runtime")
        self.assertEqual(self.work.executable_search_paths, [str(sys.executable)])
        self.assertEqual(self.work.optimizations, {"a": "b"})
        self.assertEqual(self.work.options, {"c": "d"})
        self.assertEqual(self.work.architecture, "x86_64")


class TestBaseWorkflow_is_supported(TestCase):
    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(
            language="test", dependency_manager="testframework", application_framework="appframework"
        )
        DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
        BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def setUp(self):
        self.work = self.MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[],
            optimizations={"a": "b"},
            options={"c": "d"},
            architecture="arm64",
        )

    def test_must_ignore_manifest_if_not_provided(self):
        self.work.SUPPORTED_MANIFESTS = []  # No manifest provided

        self.assertTrue(self.work.is_supported())

    def test_must_match_manifest_name(self):
        self.work.SUPPORTED_MANIFESTS = ["manifest_path", "someother_manifest"]

        self.assertTrue(self.work.is_supported())

    def test_must_match_manifest_name_from_path(self):
        self.work.manifest_path = "/path/to/manifest.json"
        self.work.SUPPORTED_MANIFESTS = ["manifest.json", "someother_manifest"]

        self.assertTrue(self.work.is_supported())

    def test_must_match_architecture_type(self):
        self.assertEqual(self.work.architecture, "arm64")

    def test_must_fail_if_manifest_not_in_list(self):
        self.work.SUPPORTED_MANIFESTS = ["someother_manifest"]

        self.assertFalse(self.work.is_supported())


class TestBaseWorkflow_run(TestCase):
    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(
            language="test", dependency_manager="testframework", application_framework="appframework"
        )
        DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
        BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def setUp(self):
        self.work = self.MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[],
            optimizations={"a": "b"},
            options={"c": "d"},
        )

    def mock_binaries(self):
        self.validator_mock = Mock()
        self.validator_mock.validate = Mock()
        self.validator_mock.validate.return_value = "/usr/bin/binary"
        self.resolver_mock = Mock()
        self.resolver_mock.exec_paths = ["/usr/bin/binary"]
        self.binaries_mock = Mock()
        self.binaries_mock.return_value = []

        self.work.get_validators = lambda: self.validator_mock
        self.work.get_resolvers = lambda: self.resolver_mock
        self.work.binaries = {
            "binary": BinaryPath(resolver=self.resolver_mock, validator=self.validator_mock, binary="binary")
        }

    def test_get_binaries(self):
        self.assertIsNotNone(self.work.binaries)
        for binary, binary_path in self.work.binaries.items():
            self.assertTrue(isinstance(binary_path, BinaryPath))

    def test_get_validator(self):
        self.assertIsNotNone(self.work.get_validators())
        for validator in self.work.get_validators():
            self.assertTrue(isinstance(validator, RuntimeValidator))

    def test_must_execute_actions_in_sequence(self):
        self.mock_binaries()
        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]
        self.work.run()

        self.assertEqual(
            action_mock.method_calls, [call.action1.execute(), call.action2.execute(), call.action3.execute()]
        )
        self.assertTrue(self.validator_mock.validate.call_count, 1)

    def test_must_fail_workflow_binary_resolution_failure(self):
        self.mock_binaries()
        action_mock = Mock()
        self.resolver_mock.exec_paths = MagicMock(side_effect=ValueError("Binary could not be resolved"))

        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]
        with self.assertRaises(WorkflowFailedError) as ex:
            self.work.run()

    def test_must_fail_workflow_binary_validation_failure(self):
        self.mock_binaries()
        self.validator_mock.validate = MagicMock(
            side_effect=MisMatchRuntimeError(language="test", required_runtime="test1", runtime_path="/usr/bin/binary")
        )

        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]
        with self.assertRaises(WorkflowFailedError) as ex:
            self.work.run()

    def test_must_raise_with_no_actions(self):
        self.mock_binaries()

        self.work.actions = []

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.work.run()

        self.assertIn("Workflow does not have any actions registered", str(ctx.exception))

    def test_must_raise_if_action_failed(self):
        self.mock_binaries()
        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]

        # Doesn't matter which action fails, but let's make the second one fail
        action_mock.action2.execute.side_effect = ActionFailedError("testfailure")

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.work.run()

        self.assertIn("testfailure", str(ctx.exception))

    def test_must_raise_if_action_crashed(self):
        self.mock_binaries()
        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]

        # This is unhandled exception
        action_mock.action1.execute.side_effect = ValueError("somevalueerror")

        with self.assertRaises(WorkflowUnknownError) as ctx:
            self.work.run()

        self.assertIn("somevalueerror", str(ctx.exception))

    def test_supply_executable_path(self):
        # Run workflow with supplied executable path to search for executables
        action_mock = Mock()

        self.work = self.MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[str(pathlib.Path(os.getcwd()).parent)],
            optimizations={"a": "b"},
            options={"c": "d"},
        )
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]
        self.mock_binaries()

        self.work.run()

    def test_must_raise_for_unknown_runtime(self):
        action_mock = Mock()
        validator_mock = Mock()
        validator_mock.validate = Mock()
        validator_mock.validate = MagicMock(side_effect=UnsupportedRuntimeError(runtime="runtime"))

        resolver_mock = Mock()
        resolver_mock.exec_paths = ["/usr/bin/binary"]
        binaries_mock = Mock()
        binaries_mock.return_value = []

        self.work.get_validators = lambda: validator_mock
        self.work.get_resolvers = lambda: resolver_mock
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]
        self.work.binaries = {"binary": BinaryPath(resolver=resolver_mock, validator=validator_mock, binary="binary")}
        with self.assertRaises(WorkflowFailedError) as ex:
            self.work.run()

        self.assertIn("Runtime runtime is not supported", str(ex.exception))

    def test_must_raise_for_incompatible_runtime_and_architecture(self):
        self.work = self.MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="python3.7",
            executable_search_paths=[str(pathlib.Path(os.getcwd()).parent)],
            optimizations={"a": "b"},
            options={"c": "d"},
        )
        action_mock = Mock()
        validator_mock = Mock()
        validator_mock.validate = Mock()
        validator_mock.validate = MagicMock(
            side_effect=UnsupportedArchitectureError(runtime="python3.7", architecture="arm64")
        )

        resolver_mock = Mock()
        resolver_mock.exec_paths = ["/usr/bin/binary"]
        binaries_mock = Mock()
        binaries_mock.return_value = []

        self.work.architecture = "arm64"
        self.work.get_validators = lambda: validator_mock
        self.work.get_resolvers = lambda: resolver_mock
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]
        self.work.binaries = {"binary": BinaryPath(resolver=resolver_mock, validator=validator_mock, binary="binary")}
        with self.assertRaises(WorkflowFailedError) as ex:
            self.work.run()

        self.assertIn("Architecture arm64 is not supported for runtime python3.7", str(ex.exception))


class TestBaseWorkflow_repr(TestCase):
    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(
            language="test", dependency_manager="testframework", application_framework="appframework"
        )
        DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
        BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def setUp(self):
        self.action1 = Mock()
        self.action2 = Mock()
        self.action3 = Mock()

        self.action1.__repr__ = Mock(return_value="Name=Action1, Purpose=COPY_SOURCE, Description=Copies source code")
        self.action2.__repr__ = Mock(
            return_value="Name=Action2, Purpose=RESOLVE_DEPENDENCIES," " Description=Resolves dependencies"
        )
        self.action3.__repr__ = Mock(return_value="Name=Action3, Purpose=COMPILE_SOURCE, " "Description=Compiles code")

        self.work = self.MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[],
            optimizations={"a": "b"},
            options={"c": "d"},
        )

    def test_must_pretty_print_workflow_info(self):
        self.work.actions = [self.action1, self.action2, self.action3]
        self.maxDiff = None

        result = str(self.work)
        expected = """Workflow=MyWorkflow
Actions=
\tName=Action1, Purpose=COPY_SOURCE, Description=Copies source code
\tName=Action2, Purpose=RESOLVE_DEPENDENCIES, Description=Resolves dependencies
\tName=Action3, Purpose=COMPILE_SOURCE, Description=Compiles code"""

        self.assertEqual(result, expected)


class TestBaseWorkflow_build_in_source(TestCase):
    def test_must_use_source_directory_if_building_in_source(self):
        class MyWorkflow(BaseWorkflow):
            __TESTING__ = True
            NAME = "MyWorkflow"
            CAPABILITY = Capability(
                language="test", dependency_manager="testframework", application_framework="appframework"
            )
            DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
            BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        source_dir = "source_dir"

        self.work = MyWorkflow(
            source_dir,
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[str(sys.executable)],
            optimizations={"a": "b"},
            options={"c": "d"},
            build_in_source=True
        )

        self.assertEqual(self.work.build_dir, source_dir)

    @parameterized.expand(
        [
            (BuildDirectory.SCRATCH, "scratch_dir"),
            (BuildDirectory.SOURCE, "source_dir"),
            (BuildDirectory.ARTIFACTS, "artifacts_dir"),
        ]
    )
    def test_must_use_correct_default_value(
        self, default_build_dir, expected_build_dir
    ):
        class MyWorkflow(BaseWorkflow):
            __TESTING__ = True
            NAME = "MyWorkflow"
            CAPABILITY = Capability(
                language="test", dependency_manager="testframework", application_framework="appframework"
            )
            DEFAULT_BUILD_DIR = default_build_dir
            BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

        self.work = MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[str(sys.executable)],
            optimizations={"a": "b"},
            options={"c": "d"},
        )

        self.assertEqual(self.work.build_dir, expected_build_dir)

    @parameterized.expand(
        [
            (True, BuildInSourceSupport.NOT_SUPPORTED, BuildDirectory.SCRATCH, "scratch_dir"),  # want to build in source but it's not supported
            (
                False,
                BuildInSourceSupport.EXCLUSIVELY_SUPPORTED,
                BuildDirectory.SOURCE,
                "source_dir"
            ),  # don't want to build in source but workflow requires it
            ("unsupported", BuildInSourceSupport.OPTIONALLY_SUPPORTED, BuildDirectory.ARTIFACTS, "artifacts_dir"),  # unsupported value passed in
        ]
    )
    def test_must_use_default_if_unsupported_value_is_provided(
        self, build_in_source_value, build_in_source_support, default_build_dir, expected_build_dir
    ):
        class MyWorkflow(BaseWorkflow):
            __TESTING__ = True
            NAME = "MyWorkflow"
            CAPABILITY = Capability(
                language="test", dependency_manager="testframework", application_framework="appframework"
            )
            DEFAULT_BUILD_DIR = default_build_dir
            BUILD_IN_SOURCE_SUPPORT = build_in_source_support

        self.work = MyWorkflow(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=[str(sys.executable)],
            optimizations={"a": "b"},
            options={"c": "d"},
            build_in_source=build_in_source_value,
        )

        self.assertEqual(self.work.build_dir, expected_build_dir)
