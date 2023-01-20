"""
Cargo Lambda specific exceptions
"""

from aws_lambda_builders.exceptions import LambdaBuilderError


class CargoLambdaExecutionException(LambdaBuilderError):
    """
    Exception raised in case Cargo Lambda execution fails.
    It will pass on the standard error output from the Cargo Lambda console.
    """

    MESSAGE = "Cargo Lambda failed: {message}"
