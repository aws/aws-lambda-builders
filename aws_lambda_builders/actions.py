"""
Definition of actions used in the workflow
"""

import logging
import shutil
import six

from aws_lambda_builders.utils import copytree

LOG = logging.getLogger(__name__)


class ActionFailedError(Exception):
    """
    Base class for exception raised when action failed to complete. Use this to express well-known failure scenarios.
    """

    pass


class Purpose(object):
    """
    Enum like object to describe the purpose of each action.
    """

    # Action is identifying dependencies, downloading, compiling and resolving them
    RESOLVE_DEPENDENCIES = "RESOLVE_DEPENDENCIES"

    # Action is copying source code
    COPY_SOURCE = "COPY_SOURCE"

    # Action is compiling source code
    COMPILE_SOURCE = "COMPILE_SOURCE"

    @staticmethod
    def has_value(item):
        return item in Purpose.__dict__.values()


class _ActionMetaClass(type):
    def __new__(mcs, name, bases, class_dict):

        cls = type.__new__(mcs, name, bases, class_dict)

        if cls.__name__ == "BaseAction":
            return cls

        # Validate class variables
        # All classes must provide a name
        if not isinstance(cls.NAME, six.string_types):
            raise ValueError("Action must provide a valid name")

        if not Purpose.has_value(cls.PURPOSE):
            raise ValueError("Action must provide a valid purpose")

        return cls


class BaseAction(six.with_metaclass(_ActionMetaClass, object)):
    """
    Base class for all actions. It does not provide any implementation.
    """

    # Every action must provide a name
    NAME = None

    # Optional description explaining what this action is about. Used to print help text
    DESCRIPTION = ""

    # What is this action meant for? Must be a valid instance of `Purpose` class
    PURPOSE = None

    def execute(self):
        """
        Runs the action. This method should complete the action, and if it fails raise appropriate exceptions.

        :raises lambda_builders.actions.ActionFailedError: Instance of this class if something went wrong with the
            action
        """
        raise NotImplementedError("execute")

    def __repr__(self):
        return "Name={}, Purpose={}, Description={}".format(self.NAME, self.PURPOSE, self.DESCRIPTION)


class CopySourceAction(BaseAction):

    NAME = "CopySource"

    DESCRIPTION = "Copying source code while skipping certain commonly excluded files"

    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, dest_dir, excludes=None):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.excludes = excludes or []

    def execute(self):
        copytree(self.source_dir, self.dest_dir, ignore=shutil.ignore_patterns(*self.excludes))
