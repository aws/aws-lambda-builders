"""
Esbuild specific exceptions
"""
from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.exceptions import LambdaBuilderError


class EsbuildExecutionError(LambdaBuilderError):
    """
    Exception raised in case esbuild execution fails.
    It will pass on the standard error output from the esbuild console.
    """

    MESSAGE = "Esbuild Failed: {message}"


class EsbuildCommandError(ActionFailedError):
    """
    Exception raised in case esbuild can't build a valid esbuild command from the given config.
    It will pass on the standard error output from the esbuild console.
    """
