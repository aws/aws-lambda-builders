"""
Collection of public exceptions raised by this library
"""


class LambdaBuilderError(Exception):

    MESSAGE = ""

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class UnsupportedManifestError(LambdaBuilderError):
    MESSAGE = "A builder for the given capabilities '{capabilities}' was not found"


class MisMatchRuntimeError(LambdaBuilderError):
    MESSAGE = (
        "{language} executable found in your path does not "
        "match runtime. "
        "\n Expected version: {required_runtime}, Found version: {runtime_path}. "
        "\n Possibly related: https://github.com/awslabs/aws-lambda-builders/issues/30"
    )


class WorkflowNotFoundError(LambdaBuilderError):
    """
    Raised when a workflow matching the given capabilities was not found
    """

    MESSAGE = (
        "Unable to find a workflow matching given capability: "
        "{language}, {dependency_manager}, {application_framework}"
    )


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
