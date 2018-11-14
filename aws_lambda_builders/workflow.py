"""
Implementation of a base workflow
"""

import os
import logging

from collections import namedtuple
import six

from aws_lambda_builders.registry import DEFAULT_REGISTRY
from aws_lambda_builders.exceptions import WorkflowFailedError, WorkflowUnknownError
from aws_lambda_builders.actions import ActionFailedError

LOG = logging.getLogger(__name__)


# Named tuple to express the capabilities supported by the builder.
# ``Language`` is the programming language. Ex: Python
# ``LangageFramework`` is the framework of particular language. Ex: PIP
# ``ApplicationFramework`` is the specific application framework used to write the code. Ex: Chalice
Capability = namedtuple('Capability', ["language", "dependency_manager", "application_framework"])


class _WorkflowMetaClass(type):
    """
    A metaclass that maintains the registry of loaded builders
    """

    def __new__(mcs, name, bases, class_dict):
        """
        Add the builder to registry when loading the class
        """

        cls = type.__new__(mcs, name, bases, class_dict)

        # We don't want to register the base classes, so we simply return here.
        # Also, skip further steps if the class is marked for testing
        if cls.__name__ == 'BaseWorkflow' or cls.__TESTING__:
            return cls

        # Validate class variables

        # All classes must provide a name
        if not isinstance(cls.NAME, six.string_types):
            raise ValueError("Workflow must provide a valid name")

        # All workflows must express their capabilities
        if not isinstance(cls.CAPABILITY, Capability):
            raise ValueError("Workflow '{}' must register valid capabilities".format(cls.NAME))

        LOG.debug("Registering workflow '%s' with capability '%s'", cls.NAME, cls.CAPABILITY)
        DEFAULT_REGISTRY[cls.CAPABILITY] = cls

        return cls


class BaseWorkflow(six.with_metaclass(_WorkflowMetaClass, object)):
    """
    Default implementation of the builder workflow. It provides several useful capabilities out-of-box that help
    minimize the scope of build actions.
    """

    # Set this property if you are in the process of testing a workflow class. This will prevent the class from
    # being added to registry.
    __TESTING__ = False

    NAME = None

    # Capabilities supported by this builder. Must be an instance of `Capability` named tuple
    CAPABILITY = None

    # Optional list of manifests file/folder names supported by this workflow.
    SUPPORTED_MANIFESTS = []

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 runtime=None,
                 optimizations=None,
                 options=None):
        """
        Initialize the builder with given arguments. These arguments together form the "public API" that each
        build action must support at the minimum.

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type artifacts_dir: str
        :param artifacts_dir:
            Path to a folder where the built artifacts should be placed

        :type scratch_dir: str
        :param scratch_dir:
            Path to a directory that the workflow can use as scratch space. Workflows are expected to use this directory
            to write temporary files instead of ``/tmp`` or other OS-specific temp directories.

        :type manifest_path: str
        :param manifest_path:
            Path to the dependency manifest

        :type runtime: str
        :param runtime:
            Optional, name of the AWS Lambda runtime that you are building for. This is sent to the builder for
            informational purposes.

        :type optimizations: dict
        :param optimizations:
            Optional dictionary of optimization flags to pass to the build action. **Not supported**.

        :type options: dict
        :param options:
            Optional dictionary of options ot pass to build action. **Not supported**.
        """

        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.scratch_dir = scratch_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.optimizations = optimizations
        self.options = options

        # Actions are registered by the subclasses as they seem fit
        self.actions = []

    def is_supported(self):
        """
        Is the given manifest supported? If the workflow exposes no manifests names, then we it is assumed that
        we don't have a restriction
        """

        if self.SUPPORTED_MANIFESTS:
            return os.path.basename(self.manifest_path) in self.SUPPORTED_MANIFESTS

        return True

    def run(self):
        """
        Actually perform the build by executing registered actions.

        :raises WorkflowFailedError: If the workflow does not contain any actions or if one of the actions ran into
            an error

        :raises WorkflowUnknownError: If one of the actions in the workflow raised an unhandled exception
        """

        LOG.debug("Running workflow '%s'", self.NAME)

        if not self.actions:
            raise WorkflowFailedError(workflow_name=self.NAME,
                                      action_name=None,
                                      reason="Workflow does not have any actions registered")

        for action in self.actions:
            action_info = "Workflow='{}',Action='{}'".format(self.NAME, action.NAME)

            LOG.info("Running %s: %s", action_info, action.DESCRIPTION)

            try:
                action.execute()

                LOG.debug("%s succeeded", action_info)

            except ActionFailedError as ex:
                LOG.debug("%s failed", action_info, exc_info=ex)

                raise WorkflowFailedError(workflow_name=self.NAME,
                                          action_name=action.NAME,
                                          reason=str(ex))
            except Exception as ex:
                LOG.debug("%s raised unhandled exception", action_info, exc_info=ex)

                raise WorkflowUnknownError(workflow_name=self.NAME,
                                           action_name=action.NAME,
                                           reason=str(ex))

    def __repr__(self):
        """
        Pretty prints information about this workflow.

        Sample output:
            Workflow=MyWorkflow
            Actions=
                Name=Action1, Purpose=COPY_SOURCE, Description=Copies source code
                Name=Action2, Purpose=RESOLVE_DEPENDENCIES, Description=Resolves dependencies
                Name=Action3, Purpose=COMPILE_SOURCE, Description=Compiles code
        """
        return "Workflow={}\nActions=\n\t{}".format(self.NAME, "\n\t".join(map(str, self.actions)))
