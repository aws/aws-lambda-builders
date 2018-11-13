
from unittest import TestCase
from mock import Mock, call
from parameterized import parameterized

from aws_lambda_builders.registry import Registry, DEFAULT_REGISTRY, get_workflow
from aws_lambda_builders.workflow import Capability
from aws_lambda_builders.exceptions import WorkflowNotFoundError


class TestRegistryEndToEnd(TestCase):

    def setUp(self):
        self.registry = Registry()

        # Since the registry does not validate whether we register a valid workflow object, we can register any fake
        # data
        self.workflow_data = "fake workflow"

    def test_must_add_item(self):
        capability = Capability(language="a", dependency_manager="b", application_framework="c")

        self.registry[capability] = self.workflow_data
        self.assertEquals(self.workflow_data, self.registry[capability])

    @parameterized.expand([
        (Capability(language=None, dependency_manager="b", application_framework="c"), ),
        (Capability(language="a", dependency_manager=None, application_framework="c"), ),
        (Capability(language="a", dependency_manager=None, application_framework=None), ),
    ])
    def test_must_add_item_with_optional_capabilities(self, capability):

        self.registry[capability] = self.workflow_data
        self.assertEquals(self.workflow_data, self.registry[capability])

    def test_must_add_multiple_items(self):
        capability1 = Capability(language="a", dependency_manager="b", application_framework="c")
        capability2 = Capability(language="d", dependency_manager="e", application_framework="f")

        self.registry[capability1] = "some data"
        self.registry[capability2] = "some other data"

        self.assertEquals(len(self.registry), 2)
        self.assertTrue(capability1 in self.registry)
        self.assertTrue(capability2 in self.registry)

    def test_fail_on_duplciate_entry(self):
        capability = Capability(language="a", dependency_manager="b", application_framework="c")

        self.registry[capability] = self.workflow_data
        self.assertEquals(self.workflow_data, self.registry[capability])

        with self.assertRaises(KeyError):
            self.registry[capability] = "some other data"

    def test_must_clear_entries(self):
        capability = Capability(language="a", dependency_manager="b", application_framework="c")

        self.registry[capability] = self.workflow_data
        self.assertEquals(len(self.registry), 1)

        self.registry.clear()

        self.assertEquals(len(self.registry), 0)


class TestRegistryLocking(TestCase):

    def setUp(self):
        self.mock_lock = Mock()
        self.registry = Registry(write_lock=self.mock_lock)

        self.capability = Capability(language="a", dependency_manager="b", application_framework="c")
        self.workflow_data = "fake workflow"

        # Always must call acquire() first before release()
        self.expected_lock_call_order = [call.acquire(), call.release()]

    def test_set_item_must_lock(self):
        self.registry[self.capability] = self.workflow_data

        self.assertEquals(self.mock_lock.method_calls, self.expected_lock_call_order)

    def test_set_item_with_duplicate_must_release_lock(self):
        self.registry[self.capability] = self.workflow_data

        # Reset any data stored on the mock, so we can capture data from the following call
        self.mock_lock.reset_mock()

        with self.assertRaises(KeyError):
            # Try register duplicate
            self.registry[self.capability] = self.workflow_data

        self.assertEquals(self.mock_lock.method_calls, self.expected_lock_call_order)

    def test_get_item_must_not_use_lock(self):
        self.registry[self.capability] = self.workflow_data
        self.mock_lock.reset_mock()

        _ = self.registry[self.capability]  # noqa: F841

        self.assertEquals(self.mock_lock.method_calls, [])

    def test_contains_must_not_use_lock(self):
        self.registry[self.capability] = self.workflow_data
        self.mock_lock.reset_mock()

        _ = self.capability in self.registry  # noqa: F841

        self.assertEquals(self.mock_lock.method_calls, [])

    def test_clear_must_lock(self):
        self.registry[self.capability] = self.workflow_data
        self.mock_lock.reset_mock()

        self.registry.clear()

        self.assertEquals(self.mock_lock.method_calls, self.expected_lock_call_order)


class TestGetWorkflow(TestCase):

    def setUp(self):
        self.registry = Registry()
        self.capability = Capability(language="a", dependency_manager="b", application_framework="c")
        self.workflow_data = "some workflow data"

    def tearDown(self):
        DEFAULT_REGISTRY.clear()

    def test_must_get_workflow_from_custom_registry(self):
        # register a workflow
        self.registry[self.capability] = self.workflow_data

        result = get_workflow(self.capability, registry=self.registry)
        self.assertEquals(result, self.workflow_data)

    def test_must_get_workflow_from_default_registry(self):
        DEFAULT_REGISTRY[self.capability] = self.workflow_data

        result = get_workflow(self.capability)
        self.assertEquals(result, self.workflow_data)

    def test_must_raise_if_workflow_not_found(self):

        # Don't register any workflow, and try querying

        with self.assertRaises(WorkflowNotFoundError):
            get_workflow(self.capability)
