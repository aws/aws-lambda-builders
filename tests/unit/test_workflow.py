
from unittest import TestCase
from mock import Mock, call

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.registry import get_workflow, DEFAULT_REGISTRY
from aws_lambda_builders.exceptions import WorkflowFailedError, WorkflowUnknownError
from aws_lambda_builders.actions import ActionFailedError


class TestRegisteringWorkflows(TestCase):

    CAPABILITY1 = Capability(language="test",
                             dependency_manager="testframework",
                             application_framework="appframework")

    CAPABILITY2 = Capability(language="test2",
                             dependency_manager="testframework2",
                             application_framework="appframework2")

    def tearDown(self):
        DEFAULT_REGISTRY.clear()

    def test_must_register_one_workflow(self):

        # Just loading the classes will register them to default registry
        class TestWorkflow(BaseWorkflow):
            NAME = "TestWorkflow"
            CAPABILITY = self.CAPABILITY1

        result_cls = get_workflow(self.CAPABILITY1)
        self.assertEquals(len(DEFAULT_REGISTRY), 1)
        self.assertEquals(result_cls, TestWorkflow)

    def test_must_register_two_workflows(self):

        class TestWorkflow1(BaseWorkflow):
            NAME = "TestWorkflow"
            CAPABILITY = self.CAPABILITY1

        class TestWorkflow2(BaseWorkflow):
            NAME = "TestWorkflow2"
            CAPABILITY = self.CAPABILITY2

        self.assertEquals(len(DEFAULT_REGISTRY), 2)
        self.assertEquals(get_workflow(self.CAPABILITY1), TestWorkflow1)
        self.assertEquals(get_workflow(self.CAPABILITY2), TestWorkflow2)

    def test_must_fail_if_name_not_present(self):

        with self.assertRaises(ValueError) as ctx:
            class TestWorkflow1(BaseWorkflow):
                CAPABILITY = self.CAPABILITY1

        self.assertEquals(len(DEFAULT_REGISTRY), 0)
        self.assertEquals(str(ctx.exception), "Workflow must provide a valid name")

    def test_must_fail_if_capabilities_not_present(self):

        with self.assertRaises(ValueError) as ctx:
            class TestWorkflow1(BaseWorkflow):
                NAME = "somename"

        self.assertEquals(len(DEFAULT_REGISTRY), 0)
        self.assertEquals(str(ctx.exception), "Workflow 'somename' must register valid capabilities")

    def test_must_fail_if_capabilities_is_wrong_type(self):

        with self.assertRaises(ValueError) as ctx:
            class TestWorkflow1(BaseWorkflow):
                NAME = "somename"
                CAPABILITY = "wrong data type"

        self.assertEquals(len(DEFAULT_REGISTRY), 0)
        self.assertEquals(str(ctx.exception), "Workflow 'somename' must register valid capabilities")


class TestBaseWorkflow_init(TestCase):

    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(language="test",
                                dependency_manager="testframework",
                                application_framework="appframework")

    def test_must_initialize_variables(self):
        self.work = self.MyWorkflow("source_dir", "artifacts_dir", "scratch_dir", "manifest_path",
                                    runtime="runtime",
                                    optimizations={"a": "b"},
                                    options={"c": "d"})

        self.assertEquals(self.work.source_dir, "source_dir")
        self.assertEquals(self.work.artifacts_dir, "artifacts_dir")
        self.assertEquals(self.work.scratch_dir, "scratch_dir")
        self.assertEquals(self.work.manifest_path, "manifest_path")
        self.assertEquals(self.work.runtime, "runtime")
        self.assertEquals(self.work.optimizations, {"a": "b"})
        self.assertEquals(self.work.options, {"c": "d"})


class TestBaseWorkflow_is_supported(TestCase):

    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(language="test",
                                dependency_manager="testframework",
                                application_framework="appframework")

    def setUp(self):
        self.work = self.MyWorkflow("source_dir", "artifacts_dir", "scratch_dir", "manifest_path",
                                    runtime="runtime",
                                    optimizations={"a": "b"},
                                    options={"c": "d"})

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

    def test_must_fail_if_manifest_not_in_list(self):
        self.work.SUPPORTED_MANIFESTS = ["someother_manifest"]

        self.assertFalse(self.work.is_supported())


class TestBaseWorkflow_run(TestCase):

    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(language="test",
                                dependency_manager="testframework",
                                application_framework="appframework")

    def setUp(self):
        self.work = self.MyWorkflow("source_dir", "artifacts_dir", "scratch_dir", "manifest_path",
                                    runtime="runtime",
                                    optimizations={"a": "b"},
                                    options={"c": "d"})

    def test_must_execute_actions_in_sequence(self):
        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]

        self.work.run()

        self.assertEquals(action_mock.method_calls, [
            call.action1.execute(), call.action2.execute(), call.action3.execute()
        ])

    def test_must_raise_with_no_actions(self):
        self.work.actions = []

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.work.run()

        self.assertIn("Workflow does not have any actions registered", str(ctx.exception))

    def test_must_raise_if_action_failed(self):
        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]

        # Doesn't matter which action fails, but let's make the second one fail
        action_mock.action2.execute.side_effect = ActionFailedError("testfailure")

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.work.run()

        self.assertIn("testfailure", str(ctx.exception))

    def test_must_raise_if_action_crashed(self):
        action_mock = Mock()
        self.work.actions = [action_mock.action1, action_mock.action2, action_mock.action3]

        # This is unhandled exception
        action_mock.action1.execute.side_effect = ValueError("somevalueerror")

        with self.assertRaises(WorkflowUnknownError) as ctx:
            self.work.run()

        self.assertIn("somevalueerror", str(ctx.exception))


class TestBaseWorkflow_repr(TestCase):

    class MyWorkflow(BaseWorkflow):
        __TESTING__ = True
        NAME = "MyWorkflow"
        CAPABILITY = Capability(language="test",
                                dependency_manager="testframework",
                                application_framework="appframework")

    def setUp(self):
        self.action1 = Mock()
        self.action2 = Mock()
        self.action3 = Mock()

        self.action1.__repr__ = Mock(return_value="Name=Action1, Purpose=COPY_SOURCE, Description=Copies source code")
        self.action2.__repr__ = Mock(return_value="Name=Action2, Purpose=RESOLVE_DEPENDENCIES,"
                                                  " Description=Resolves dependencies")
        self.action3.__repr__ = Mock(return_value="Name=Action3, Purpose=COMPILE_SOURCE, "
                                                  "Description=Compiles code")

        self.work = self.MyWorkflow("source_dir", "artifacts_dir", "scratch_dir", "manifest_path",
                                    runtime="runtime",
                                    optimizations={"a": "b"},
                                    options={"c": "d"})

    def test_must_pretty_print_workflow_info(self):
        self.work.actions = [self.action1, self.action2, self.action3]
        self.maxDiff = None

        result = str(self.work)
        expected = """Workflow=MyWorkflow
Actions=
\tName=Action1, Purpose=COPY_SOURCE, Description=Copies source code
\tName=Action2, Purpose=RESOLVE_DEPENDENCIES, Description=Resolves dependencies
\tName=Action3, Purpose=COMPILE_SOURCE, Description=Compiles code"""

        self.assertEquals(result, expected)
