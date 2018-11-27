"""
Collection of public exceptions raised by this library
"""


class LambdaBuilderError(Exception):

    MESSAGE = ''

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class UnsupportedManifestError(LambdaBuilderError):
    MESSAGE = "A builder for the given capabilities '{capabilities}' was not found"


class MisMatchRuntimeError(LambdaBuilderError):
    MESSAGE = "A runtime version mismatch was found for the given language " \
              "'{language}', required runtime '{required_runtime}'"


class WorkflowNotFoundError(LambdaBuilderError):
    """
    Raised when a workflow matching the given capabilities was not found
    """
    MESSAGE = "Unable to find a workflow matching given capability: " \
              "{language}, {dependency_manager}, {application_framework}"


class WorkflowFailedError(LambdaBuilderError):
    """
    Raised when the build failed, for well-known cases
    """
    MESSAGE = "{workflow_name}:{action_name} - {reason}"


class WorkflowUnknownError(LambdaBuilderError):
    """
    Raised when the build ran into an unexpected error
    """
    MESSAGE = "{workflow_name}:{action_name} - {reason}"
