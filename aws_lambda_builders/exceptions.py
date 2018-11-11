"""
Collection of public exceptions raised by this library
"""


class LambdaBuilderError(Exception):

    MESSAGE = ''

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class UnsupportedManifestError(LambdaBuilderError):
    MESSAGE = "A builder for the given capabilities '{capabilities}' was not found"


class WorkflowNotFoundError(LambdaBuilderError):
    """
    Raised when a workflow matching the given capabilities was not found
    """
    MESSAGE = "Unable to find a workflow matching given capability: " \
              "{language}, {language_framework}, {application_framework}"


class WorkflowFailedError(LambdaBuilderError):
    """
    Raised when the build failed, for well-known cases
    """
    MESSAGE = "'{workflow_name}' workflow failed: {reason}"


class WorkflowError(LambdaBuilderError):
    """
    Raised when the build ran into an unexpected error
    """
    MESSAGE = "'{workflow_name}' workflow ran into an error: {reason}"
