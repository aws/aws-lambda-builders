"""
Python PIP Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator

from .actions import PythonPipBuildAction


class PythonPipWorkflow(BaseWorkflow):

    NAME = "PythonPipBuilder"

    CAPABILITY = Capability(language="python", dependency_manager="pip", application_framework=None)

    # Common source files to exclude from build artifacts output
    # Trimmed version of https://github.com/github/gitignore/blob/master/Python.gitignore
    EXCLUDED_FILES = (
        ".aws-sam",
        ".chalice",
        ".git",
        # Compiled files
        "*.pyc",
        "__pycache__",
        "*.so",
        # Distribution / packaging
        ".Python",
        "*.egg-info",
        "*.egg",
        # Installer logs
        "pip-log.txt",
        "pip-delete-this-directory.txt",
        # Unit test / coverage reports
        "htmlcov",
        ".tox",
        ".nox",
        ".coverage",
        ".cache",
        ".pytest_cache",
        # pyenv
        ".python-version",
        # mypy, Pyre
        ".mypy_cache",
        ".dmypy.json",
        ".pyre",
        # environments
        ".env",
        ".venv",
        "venv",
        "venv.bak",
        "env.bak",
        "ENV",
        # Editors
        # TODO: Move the commonly ignored files to base class
        ".vscode",
        ".idea",
    )

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, **kwargs):

        super(PythonPipWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        self.actions = [
            PythonPipBuildAction(artifacts_dir, scratch_dir, manifest_path, runtime, binaries=self.binaries),
            CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
        ]

    def get_validators(self):
        return [PythonRuntimeValidator(runtime=self.runtime)]
