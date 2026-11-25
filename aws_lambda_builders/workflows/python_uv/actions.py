"""
Action to resolve Python dependencies using UV
"""

import logging
import os
import shutil
from typing import Optional

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.architecture import X86_64

from .exceptions import LockFileError, MissingUvError, UvBuildError, UvInstallationError
from .packager import PythonUvDependencyBuilder, SubprocessUv, UvRunner
from .utils import OSUtils, UvConfig

LOG = logging.getLogger(__name__)


class PythonUvBuildAction(BaseAction):
    """Action for building Python dependencies using UV."""

    NAME = "ResolveDependencies"
    DESCRIPTION = "Installing dependencies using UV"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES
    LANGUAGE = "python"

    def __init__(
        self,
        artifacts_dir,
        scratch_dir,
        manifest_path,
        runtime,
        dependencies_dir,
        binaries,
        architecture=X86_64,
        config: Optional[UvConfig] = None,
    ):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.runtime = runtime
        self.dependencies_dir = dependencies_dir
        self.binaries = binaries
        self.architecture = architecture
        self.config = config or UvConfig()

        self._os_utils = OSUtils()

    def execute(self) -> None:
        """Execute the build action for Python UV workflows."""
        # Initialize UV components
        uv_subprocess = SubprocessUv(osutils=self._os_utils)
        uv_runner = UvRunner(uv_subprocess=uv_subprocess, osutils=self._os_utils)

        # Create main package builder
        package_builder = PythonUvDependencyBuilder(
            osutils=self._os_utils,
            runtime=self.runtime,
            uv_runner=uv_runner,
        )

        try:
            # Determine target directory
            target_artifact_dir = self.artifacts_dir
            if self.dependencies_dir:
                target_artifact_dir = self.dependencies_dir

            # Build dependencies
            package_builder.build_dependencies(
                artifacts_dir_path=target_artifact_dir,
                scratch_dir_path=self.scratch_dir,
                manifest_path=self.manifest_path,
                architecture=self.architecture,
                config=self.config,
            )
        except (LockFileError, MissingUvError, UvInstallationError, UvBuildError) as ex:
            raise ActionFailedError(str(ex))


class PythonUvCompileSourceAction(BaseAction):
    """Action for compiling the function's own source to bytecode, once it is in the artifacts directory."""

    NAME = "CompileSource"
    DESCRIPTION = "Compiling source to bytecode"
    PURPOSE = Purpose.COMPILE_SOURCE
    LANGUAGE = "python"

    def __init__(self, source_dir, artifacts_dir, runtime, excludes=None):
        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.runtime = runtime
        self.excludes = excludes or []

        self._os_utils = OSUtils()

    def execute(self) -> None:
        """Compile what CopySourceAction copied; the dependency build has already compiled the rest."""
        # Match CopySourceAction: a missing source was skipped there, so there is nothing to compile
        if not os.path.isdir(self.source_dir):
            return

        names = os.listdir(self.source_dir)
        ignored = shutil.ignore_patterns(*self.excludes)(self.source_dir, names)
        copied = [os.path.join(self.artifacts_dir, name) for name in sorted(names) if name not in ignored]
        paths = [path for path in copied if os.path.isdir(path) or (path.endswith(".py") and os.path.isfile(path))]
        if not paths:
            return

        python_version = self.runtime.replace("python", "") if self.runtime else None
        try:
            uv_runner = UvRunner(uv_subprocess=SubprocessUv(osutils=self._os_utils), osutils=self._os_utils)
        except MissingUvError as ex:
            # Only reached when no dependencies were installed. Bytecode is optional, so don't fail the build
            LOG.warning("Skipping bytecode compilation of the source: %s", ex)
            return
        uv_runner.compile_bytecode(python_version, paths)
