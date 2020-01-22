"""
Python pip specific workflow exceptions.
"""
from aws_lambda_builders.exceptions import LambdaBuilderError


class MissingPipError(LambdaBuilderError):
    MESSAGE = "pip executable not found in your python environment at {python_path}"
