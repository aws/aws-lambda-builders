"""
Definition of actions used in the workflow
"""


class ActionFailedError(Exception):
    """
    Base class for exception raised when action failed to complete. Use this to express well-known failure scenarios.
    """
    # TODO: Do we need a `error_code` of some sorts here? If so, we should create a named list of error codes.
    pass


class ActionTypes(object):
    RESOLVE_DEPENDENCIES = "RESOLVE_DEPENDENCIES"
    DOWNLOAD_DEPENDENCIES = "DOWNLOAD_DEPENDENCIES"
    COMPILE_DEPENDENCIES = "COMPILE_DEPENDENCIES"
    COPY_SOURCE = "COPY_SOURCE"
    COMPILE_SOURCE = "COMPILE_SOURCE"


class BaseAction(object):
    """
    Base class for all actions. It does not provide any implementation.
    """

    NAME = 'BaseAction'

    TYPE = None

    def execute(self):
        """
        Runs the action. This method should complete the action, and if it fails raise appropriate exceptions.

        :raises lambda_builders.actions.ActionFailedError: Instance of this class if something went wrong with the
            action
        """
        raise NotImplementedError()


class CopySourceAction(BaseAction):

    NAME = 'CopySourceAction'

    def __init__(self, source_dir, dest_dir, excludes=None):
        pass

    def execute(self):
        pass
