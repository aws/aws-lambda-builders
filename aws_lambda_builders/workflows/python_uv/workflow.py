"""
Python UV Workflow
"""

import logging

from aws_lambda_builders.actions import CleanUpAction, CopySourceAction
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability

from .actions import CopyDependenciesAction, PythonUvBuildAction
from .utils import OSUtils, detect_uv_manifest

LOG = logging.getLogger(__name__)


class PythonUvWorkflow(BaseWorkflow):
    """
    Workflow for building Python projects using UV.

    This workflow supports multiple manifest types:
    - uv.lock (UV lock file for exact reproducible builds)
    - pyproject.toml (modern Python projects with UV support)
    - requirements.txt (traditional pip format)
    - requirements-*.txt (environment-specific requirements)

    The workflow uses these BaseWorkflow contract properties:
    - download_dependencies: Whether to download/install dependencies (default: True)
    - dependencies_dir: Optional separate directory for dependencies (default: None)
    - combine_dependencies: Whether to copy dependencies to artifacts dir (default: True)
    """

    NAME = "PythonUvBuilder"

    CAPABILITY = Capability(language="python", dependency_manager="uv", application_framework=None)

    # Common source files to exclude from build artifacts output
    # Based on Python PIP workflow with UV-specific additions
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
        # UV specific
        ".uv-cache",
        "uv.lock.bak",
        # Editors
        ".vscode",
        ".idea",
    )

    PYTHON_VERSION_THREE = "3"

    DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.NOT_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):
        super(PythonUvWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        # Auto-detect manifest if not provided or doesn't exist
        if not manifest_path or not osutils.file_exists(manifest_path):
            detected_manifest = detect_uv_manifest(source_dir)
            if detected_manifest:
                manifest_path = detected_manifest
                LOG.info(f"Auto-detected manifest file: {manifest_path}")
            else:
                LOG.warning(
                    "No UV-compatible manifest file found (pyproject.toml, requirements.txt). "
                    "Continuing the build without dependencies."
                )
                manifest_path = None

        self._setup_build_actions(source_dir, artifacts_dir, scratch_dir, manifest_path, runtime)

    def _setup_build_actions(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime):
        """
        Set up the build actions based on configuration.

        Hybrid approach (matches python_pip workflow):
        - Simple case (dependencies_dir=None): Install deps directly to artifacts_dir, copy source
        - Advanced case (dependencies_dir provided): Install to dependencies_dir, copy deps, copy source

        This provides the best of both worlds - simple by default, flexible when needed.
        """
        self.actions = []

        # Build dependencies if we have a manifest and download_dependencies is enabled
        if manifest_path and self.download_dependencies:
            # Determine target: dependencies_dir if provided, otherwise artifacts_dir (hybrid approach)
            target_dir = self.dependencies_dir if self.dependencies_dir else artifacts_dir

            if self.dependencies_dir:
                # Advanced case: Clean up the dependencies folder before installing
                self.actions.append(CleanUpAction(self.dependencies_dir))

            self.actions.append(
                PythonUvBuildAction(
                    target_dir,  # Install to dependencies_dir OR artifacts_dir
                    scratch_dir,
                    manifest_path,
                    runtime,
                    self.dependencies_dir,  # Pass for action's internal logic
                    binaries=self.binaries,
                    architecture=self.architecture,
                )
            )

        # Advanced case: Copy dependencies from dependencies_dir to artifacts_dir if configured
        if self.dependencies_dir and self.combine_dependencies:
            self.actions.append(CopyDependenciesAction(self.dependencies_dir, artifacts_dir))

        # Always copy source code (final step)
        self.actions.append(CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES))

    def get_resolvers(self):
        """
        Get path resolvers for finding Python and UV binaries.

        Returns specialized Python path resolver that looks for additional binaries
        in addition to the language specific binary.
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
        """Get additional Python binaries to search for."""
        # python3 is an additional binary that has to be considered in addition to the original python binary,
        # when the specified python runtime is 3.x
        major, _ = self.runtime.replace(self.CAPABILITY.language, "").split(".")
        return [f"{self.CAPABILITY.language}{major}"] if major == self.PYTHON_VERSION_THREE else None

    def get_validators(self):
        """Get runtime validators.

        UV has robust built-in Python version handling and can automatically
        find, download, and manage Python versions. Unlike pip, UV doesn't need
        external validation of Python runtime paths.
        """
        return []
