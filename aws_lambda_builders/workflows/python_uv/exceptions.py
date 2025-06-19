"""
Python UV specific workflow exceptions.
"""

from aws_lambda_builders.exceptions import LambdaBuilderError


class MissingUvError(LambdaBuilderError):
    """Exception raised when UV executable is not found."""

    MESSAGE = "uv executable not found in your environment. Please install uv: https://docs.astral.sh/uv/getting-started/installation/"


class UvInstallationError(LambdaBuilderError):
    """Exception raised when UV installation or setup fails."""

    MESSAGE = "Failed to install dependencies using uv: {reason}"


class UvResolutionError(LambdaBuilderError):
    """Exception raised when UV dependency resolution fails."""

    MESSAGE = "UV dependency resolution failed: {reason}"


class UvBuildError(LambdaBuilderError):
    """Exception raised when UV package build fails."""

    MESSAGE = "UV package build failed: {reason}"


class LockFileError(LambdaBuilderError):
    """Exception raised when lock file operations fail."""

    MESSAGE = "Lock file operation failed: {reason}"


class ManifestNotFoundError(LambdaBuilderError):
    """Exception raised when no supported manifest file is found."""

    MESSAGE = "No supported dependency manifest found. Expected one of: {supported_manifests}"
