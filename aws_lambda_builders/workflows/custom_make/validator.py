"""
Custom Make Runtime Validation
"""

from aws_lambda_builders.validator import RuntimeValidator


class CustomMakeRuntimeValidator(RuntimeValidator):
    """
    Default runtime validator for CustomMake workflow
    """

    def __init__(self, runtime, architecture):
        super(CustomMakeRuntimeValidator, self).__init__(runtime, architecture)
        self._valid_runtime_path = None

    def validate(self, runtime_path):
        self._runtime_path = runtime_path
        return runtime_path
