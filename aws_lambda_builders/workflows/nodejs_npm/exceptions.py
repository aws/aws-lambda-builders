"""
Exceptions for the Node.js workflow
"""


from aws_lambda_builders.exceptions import LambdaBuilderError


class NpmExecutionError(LambdaBuilderError):
    """
    Exception raised in case NPM execution fails.
    It will pass on the standard error output from the NPM console.
    """

    MESSAGE = "NPM Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))
