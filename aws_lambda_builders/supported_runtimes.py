"""
Centralized definition of supported AWS Lambda runtimes.

This module provides a single source of truth for all supported runtimes
across the aws-lambda-builders package.
"""

from aws_lambda_builders.architecture import ARM64, X86_64

# Node.js runtimes
NODEJS_RUNTIMES = [
    "nodejs16.x",
    "nodejs18.x",
    "nodejs20.x",
    "nodejs22.x",
    "nodejs24.x",
]

# Python runtimes
PYTHON_RUNTIMES = [
    "python3.8",
    "python3.9",
    "python3.10",
    "python3.11",
    "python3.12",
    "python3.13",
    "python3.14",
]

# Ruby runtimes
RUBY_RUNTIMES = [
    "ruby3.2",
    "ruby3.3",
    "ruby3.4",
]

# Java runtimes
JAVA_RUNTIMES = [
    "java8",
    "java11",
    "java17",
    "java21",
    "java25",
]

# Go runtimes
GO_RUNTIMES = [
    "go1.x",
]

# .NET runtimes
DOTNET_RUNTIMES = [
    "dotnet6",
    "dotnet8",
    "dotnet10",
]

# Custom runtimes
CUSTOM_RUNTIMES = ["provided", "provided.al2", "provided.al2023"]

# Combined list of all supported runtimes
ALL_RUNTIMES = (
    NODEJS_RUNTIMES + PYTHON_RUNTIMES + RUBY_RUNTIMES + JAVA_RUNTIMES + GO_RUNTIMES + DOTNET_RUNTIMES + CUSTOM_RUNTIMES
)

# Runtime to architecture mapping
# All current runtimes support both ARM64 and X86_64
RUNTIME_ARCHITECTURES = {runtime: [ARM64, X86_64] for runtime in ALL_RUNTIMES}
