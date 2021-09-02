"""
Python PIP Workflow
"""
import logging

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator

from .actions import PythonPipBuildAction
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class PythonPipWorkflow(BaseWorkflow):

    NAME = "PythonPipBuilder"

    CAPABILITY = Capability(language="python", dependency_manager="pip", application_framework=None)

    # Common source files to exclude from build artifacts output
    # Trimmed version of https://github.com/github/gitignore/blob/master/Python.gitignore
    EXCLUDED_FILES = (
        ".aws-sam",
        ".chalice",
        ".git",
        ".gitignore",
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
        "env",
        # Editors
        # TODO: Move the commonly ignored files to base class
        ".vscode",
        ".idea",
    )

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(PythonPipWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        if not self.download_dependencies and not self.dependencies_dir:
            LOG.info(
                "download_dependencies is false and the dependencies_dir is not exists, just copying the source files "
                "into the artifacts directory "
            )

        self.actions = []
        if osutils.file_exists(manifest_path):
            # If a requirements.txt exists, run pip builder before copy action.
            if self.download_dependencies:
                self.actions.append(
                    PythonPipBuildAction(
                        artifacts_dir,
                        scratch_dir,
                        manifest_path,
                        runtime,
                        self.dependencies_dir,
                        binaries=self.binaries,
                    )
                )
            # if dependencies folder is provided, copy dependencies from dependencies folder to build folder
            if self.dependencies_dir:
                self.actions.append(
                    CopySourceAction(self.dependencies_dir, artifacts_dir, excludes=self.EXCLUDED_FILES)
                )

        else:
            LOG.warning("requirements.txt file not found. Continuing the build without dependencies.")

        self.actions.append(CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES))

    def get_validators(self):
        return [PythonRuntimeValidator(runtime=self.runtime)]
