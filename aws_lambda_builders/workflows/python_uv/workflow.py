"""
Python UV Workflow
"""

import logging
import os

from aws_lambda_builders.actions import CleanUpAction, CopyDependenciesAction, CopySourceAction
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability

from .actions import PythonUvBuildAction
from .utils import OSUtils, UvConfig, detect_uv_manifest

LOG = logging.getLogger(__name__)

# Build options (from sam-cli Metadata.BuildProperties) and their expected types
UV_OPTIONS = {
    "uv_groups": list,
    "uv_extras": list,
    "uv_all_extras": bool,
    "uv_prune": list,
}


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

        config = self._uv_config_from_options(manifest_path)
        self._setup_build_actions(source_dir, artifacts_dir, scratch_dir, manifest_path, runtime, config)

    def _fail(self, reason):
        # Same action name BaseWorkflow uses for runtime validation errors
        raise WorkflowFailedError(workflow_name=self.NAME, action_name="Validation", reason=reason)

    def _uv_config_from_options(self, manifest_path):
        """Build the UvConfig from the uv_* build options, rejecting anything invalid."""
        options = self.options if isinstance(self.options, dict) else {}
        unknown = sorted(key for key in options if key.startswith("uv_") and key not in UV_OPTIONS)
        if unknown:
            self._fail(f"Unknown uv build option(s): {', '.join(unknown)}. Supported: {', '.join(UV_OPTIONS)}")

        values = {key: options[key] for key in UV_OPTIONS if options.get(key) is not None}
        for key, value in values.items():
            if UV_OPTIONS[key] is bool:
                valid = isinstance(value, bool)
            else:
                valid = isinstance(value, list) and all(isinstance(item, str) and item for item in value)
            if not valid:
                expected = "true or false" if UV_OPTIONS[key] is bool else "a list of non-empty strings"
                self._fail(f"Build option {key} must be {expected}, got {value!r}")

        if values.get("uv_all_extras") and values.get("uv_extras"):
            self._fail("Build options uv_extras and uv_all_extras cannot be used together")

        if not any(values.values()):
            return UvConfig()

        if not manifest_path or os.path.basename(manifest_path) != "pyproject.toml":
            self._fail(
                f"Build options {', '.join(sorted(values))} need a pyproject.toml project, "
                f"but this build uses {os.path.basename(manifest_path) if manifest_path else 'no manifest'}"
            )

        return UvConfig(
            groups=values.get("uv_groups"),
            extras=values.get("uv_extras"),
            all_extras=values.get("uv_all_extras", False),
            prune=values.get("uv_prune"),
        )

    def _setup_build_actions(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime, config=None):
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
                    config=config,
                )
            )

        # Advanced case: copy dependencies from dependencies_dir to artifacts_dir if configured.
        # Dependencies were installed into dependencies_dir above, so that is the copy source
        # (artifact_dir) and artifacts_dir is the destination.
        if self.dependencies_dir and self.combine_dependencies:
            self.actions.append(
                CopyDependenciesAction(
                    source_dir=source_dir,
                    artifact_dir=self.dependencies_dir,
                    destination_dir=artifacts_dir,
                    maintain_symlinks=False,
                )
            )

        # Always copy source code (final step)
        self.actions.append(CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES))

    def get_resolvers(self):
        """
        Get path resolvers for the workflow.

        UV has robust built-in Python version handling and can automatically
        find, download, and manage Python versions. Unlike pip-based workflows,
        UV doesn't need external Python binary resolution.
        """
        return []

    def get_validators(self):
        """Get runtime validators.

        UV has robust built-in Python version handling and can automatically
        find, download, and manage Python versions. Unlike pip, UV doesn't need
        external validation of Python runtime paths.
        """
        return []
