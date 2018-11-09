
class BaseAction(object):
    """
    Base class for all actions. It does not provide any implementation.
    """

    NAME = 'BaseAction'

    def execute(self):
        """
        The builder will run this method on each action. This method should complete the action, and if it fails
        raise appropriate exceptions.

        :raises lambda_builders.exceptions.ActionError: Instance of this class if something went wrong with the
            action
        """
        raise NotImplementedError()


class CopySourceAction(BaseAction):

    def __init__(self, source_dir, dest_dir, excludes=None):
        pass

    def execute(self):
        pass