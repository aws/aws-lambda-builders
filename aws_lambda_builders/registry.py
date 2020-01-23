"""
Registry of auto-discovered workflows. Classes and methods in this module are thread-safe.
"""

import threading

from aws_lambda_builders.exceptions import WorkflowNotFoundError


class Registry(object):
    """
    Stores a registry of workflows. Only one workflow matching a given capability can be stored. If attempting to
    register two workflows for same capability, it will raise an exception.

    This class is thread-safe for multiple writers (ie. registers happening simultaneously from different threads).
    """

    def __init__(self, write_lock=None):
        self._write_lock = write_lock or threading.Lock()
        self._data = {}

    def __getitem__(self, capability):
        key = self._make_key(capability)
        return self._data[key]

    def __setitem__(self, capability, value):

        key = self._make_key(capability)

        try:
            self._write_lock.acquire()

            if key in self._data:
                raise KeyError("A workflow with given capabilities '{}' is already registered".format(key))

            self._data[key] = value

        finally:
            self._write_lock.release()

    def __contains__(self, capability):
        key = self._make_key(capability)
        return key in self._data

    def __len__(self):
        return len(self._data)

    def clear(self):
        try:
            self._write_lock.acquire()
            self._data.clear()
        finally:
            self._write_lock.release()

    @staticmethod
    def _make_key(capability):
        """
        Given the capabilities, generate a string that can be used as the key for the registry object
        """

        # Key is created by concatenating the capabilites data with underscore.
        # This delimiter is positional ie. if a value is not provided, the delimiter still needs to exist in the key.
        # This helps us be forwards compatible with new capabilities
        return "_".join(
            [capability.language or "", capability.dependency_manager or "", capability.application_framework or ""]
        ).lower()


# Built-in registry of workflows.
DEFAULT_REGISTRY = Registry()


def get_workflow(capability, registry=DEFAULT_REGISTRY):
    """
    Find and return a workflow class capable of acting on the given combination of capabilities

    :type capability: aws_lambda_builders.workflow.capabilities
    :param capability:
        The capabilities you want from this workflow

    :type registry: aws_lambda_builders.registry.Registry
    :param registry:
        Registry to fetch the workflow from

    :rtype: aws_lambda_builders.workflow.BaseWorkflow
    :return:
        A workflow class that has the given capabilities. Note: This returns a class and not an instance of the class.

    :raises WorkflowNotFoundError: If a workflow with given capabilities was not found
    """

    if capability not in registry:
        raise WorkflowNotFoundError(
            language=capability.language,
            dependency_manager=capability.dependency_manager,
            application_framework=capability.application_framework,
        )

    return registry[capability]
