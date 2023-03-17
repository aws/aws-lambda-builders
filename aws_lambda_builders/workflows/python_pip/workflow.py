"""
Python PIP Workflow
"""
import logging

from aws_lambda_builders.actions import CleanUpAction, CopySourceAction, LinkSourceAction
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator

from .actions import PythonPipBuildAction
from .utils import OSUtils, is_experimental_build_improvements_enabled

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

    PYTHON_VERSION_THREE = "3"

    DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.NOT_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):
        super(PythonPipWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        if not self.download_dependencies and not self.dependencies_dir:
            LOG.info(
                "download_dependencies is False and dependencies_dir is None. Copying the source files into the "
                "artifacts directory. "
            )

        self.actions = []
        if not osutils.file_exists(manifest_path):
            LOG.warning("requirements.txt file not found. Continuing the build without dependencies.")
            self.actions.append(CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES))
            return

        # If a requirements.txt exists, run pip builder before copy action.
        if self.download_dependencies:
            if self.dependencies_dir:
                # clean up the dependencies folder before installing
                self.actions.append(CleanUpAction(self.dependencies_dir))
            self.actions.append(
                PythonPipBuildAction(
                    artifacts_dir,
                    scratch_dir,
                    manifest_path,
                    runtime,
                    self.dependencies_dir,
                    binaries=self.binaries,
                    architecture=self.architecture,
                )
            )
        # if dependencies folder is provided, copy dependencies from dependencies folder to build folder
        # if combine_dependencies is false, will not copy the dependencies from dependencies folder to artifact
        # folder
        if self.dependencies_dir and self.combine_dependencies:
            # when copying downloaded dependencies back to artifacts folder, don't exclude anything
            # symlinking python dependencies is disabled for now since it is breaking sam local commands
            if False and is_experimental_build_improvements_enabled(self.experimental_flags):
                self.actions.append(LinkSourceAction(self.dependencies_dir, artifacts_dir))
            else:
                self.actions.append(CopySourceAction(self.dependencies_dir, artifacts_dir))

        self.actions.append(CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES))

    def get_resolvers(self):
        """
        Specialized Python path resolver that looks for additional binaries in addition to the language specific binary.
        """
        return [
            PathResolver(
                runtime=self.runtime,
                binary=self.CAPABILITY.language,
                additional_binaries=self._get_additional_binaries(),
                executable_search_paths=self.executable_search_paths,
            )
        ]

    def _get_additional_binaries(self):
        # python3 is an additional binary that has to be considered in addition to the original python binary, when
        # the specified python runtime is 3.x
        major, _ = self.runtime.replace(self.CAPABILITY.language, "").split(".")
        return [f"{self.CAPABILITY.language}{major}"] if major == self.PYTHON_VERSION_THREE else None

    def get_validators(self):
        return [PythonRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
