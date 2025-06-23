"""
UV-based Python dependency packager for AWS Lambda
"""

import logging
import os
from typing import Dict, List, Optional

from aws_lambda_builders.architecture import ARM64, X86_64

from .exceptions import LockFileError, MissingUvError, UvBuildError, UvInstallationError
from .utils import OSUtils, UvConfig, get_uv_version

LOG = logging.getLogger(__name__)


class SubprocessUv:
    """Low-level interface for executing UV commands via subprocess."""

    def __init__(self, osutils: Optional[OSUtils] = None):
        if osutils is None:
            osutils = OSUtils()
        self._osutils = osutils
        self._uv_executable = self._find_uv_executable()

    def _find_uv_executable(self) -> str:
        """Find UV executable in PATH."""
        uv_path = self._osutils.which("uv")
        if not uv_path:
            raise MissingUvError()
        return uv_path

    @property
    def uv_executable(self) -> str:
        """Get UV executable path."""
        return self._uv_executable

    def run_uv_command(self, args: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> tuple:
        """
        Execute UV command with given arguments.

        Args:
            args: UV command arguments
            cwd: Working directory
            env: Environment variables

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = [self._uv_executable] + args
        LOG.debug("Executing UV command: %s", " ".join(cmd))

        rc, stdout, stderr = self._osutils.run_subprocess(cmd, cwd=cwd, env=env)

        LOG.debug("UV command return code: %d", rc)
        LOG.debug("UV stdout: %s", stdout)
        LOG.debug("UV stderr: %s", stderr)

        return rc, stdout, stderr


class UvRunner:
    """High-level wrapper around UV operations."""

    def __init__(self, uv_subprocess: Optional[SubprocessUv] = None, osutils: Optional[OSUtils] = None):
        if osutils is None:
            osutils = OSUtils()
        if uv_subprocess is None:
            uv_subprocess = SubprocessUv(osutils)

        self._uv = uv_subprocess
        self._osutils = osutils

    @property
    def uv_version(self) -> Optional[str]:
        """Get UV version."""
        return get_uv_version(self._uv.uv_executable, self._osutils)

    def sync_dependencies(
        self,
        target_dir: str,
        scratch_dir: str,
        config: Optional[UvConfig] = None,
        python_version: Optional[str] = None,
        platform: Optional[str] = None,
        architecture: Optional[str] = None,
        manifest_path: Optional[str] = None,
        project_dir: Optional[str] = None,
    ) -> None:
        """
        Sync dependencies using UV.

        Args:
            target_dir: Directory to install dependencies
            scratch_dir: Scratch directory for temporary operations
            config: UV configuration options
            python_version: Target Python version (e.g., "3.9")
            platform: Target platform (e.g., "linux")
            architecture: Target architecture (e.g., "x86_64")
            manifest_path: Path to dependency manifest file (for backwards compatibility)
            project_dir: Project directory containing pyproject.toml and uv.lock
        """
        if config is None:
            config = UvConfig()

        # Determine project directory
        if project_dir:
            working_dir = project_dir
        elif manifest_path:
            # Backwards compatibility: derive project dir from manifest path
            working_dir = os.path.dirname(manifest_path)
        else:
            raise ValueError("Either project_dir or manifest_path must be provided")

        # Ensure UV cache is configured to use scratch directory
        if not config.cache_dir:
            config.cache_dir = os.path.join(scratch_dir, "uv-cache")
            # Use exist_ok equivalent for osutils
            if not os.path.exists(config.cache_dir):
                self._osutils.makedirs(config.cache_dir)

        args = ["sync"]

        # Add configuration arguments
        args.extend(config.to_uv_args())

        # Add platform-specific arguments
        if python_version:
            args.extend(["--python", python_version])

        # Note: uv sync doesn't support --platform or --arch arguments
        # It uses the current environment's platform by default

        # Execute UV sync - it automatically finds pyproject.toml and uv.lock in working_dir
        rc, stdout, stderr = self._uv.run_uv_command(args, cwd=working_dir)

        if rc != 0:
            raise UvInstallationError(reason=f"UV sync failed: {stderr}")

        # Copy dependencies from virtual environment to target directory
        # uv sync creates a .venv directory in the project directory
        venv_site_packages = os.path.join(working_dir, ".venv", "lib", f"python{python_version}", "site-packages")

        if os.path.exists(venv_site_packages):
            # Copy all site-packages contents to target directory
            import shutil

            for item in os.listdir(venv_site_packages):
                src_path = os.path.join(venv_site_packages, item)
                dst_path = os.path.join(target_dir, item)

                if os.path.isdir(src_path):
                    self._osutils.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)

    def install_requirements(
        self,
        requirements_path: str,
        target_dir: str,
        scratch_dir: str,
        config: Optional[UvConfig] = None,
        python_version: Optional[str] = None,
        platform: Optional[str] = None,
        architecture: Optional[str] = None,
    ) -> None:
        """
        Install requirements using UV pip interface.

        Args:
            requirements_path: Path to requirements.txt file
            target_dir: Directory to install dependencies
            scratch_dir: Scratch directory for temporary operations
            config: UV configuration options
            python_version: Target Python version
            platform: Target platform
            architecture: Target architecture
        """
        if config is None:
            config = UvConfig()

        # Ensure UV cache is configured to use scratch directory
        if not config.cache_dir:
            config.cache_dir = os.path.join(scratch_dir, "uv-cache")
            # Use exist_ok equivalent for osutils
            if not os.path.exists(config.cache_dir):
                self._osutils.makedirs(config.cache_dir)

        args = ["pip", "install"]

        # Add requirements file
        args.extend(["-r", requirements_path])

        # Add target directory
        args.extend(["--target", target_dir])

        # Add configuration arguments
        args.extend(config.to_uv_args())

        # Add platform-specific arguments
        if python_version:
            args.extend(["--python-version", python_version])

        if platform and architecture:
            # UV pip install uses --python-platform format
            # Map Lambda architectures to UV platform strings
            platform_mapping = {
                ("linux", X86_64): "x86_64-unknown-linux-gnu",
                ("linux", ARM64): "aarch64-unknown-linux-gnu",
            }

            platform_key = (platform, architecture)
            if platform_key in platform_mapping:
                args.extend(["--python-platform", platform_mapping[platform_key]])

        # Execute UV pip install
        rc, stdout, stderr = self._uv.run_uv_command(args)

        if rc != 0:
            raise UvInstallationError(reason=f"UV pip install failed: {stderr}")


class PythonUvDependencyBuilder:
    """High-level dependency builder that orchestrates UV operations."""

    def __init__(
        self, osutils: Optional[OSUtils] = None, runtime: Optional[str] = None, uv_runner: Optional[UvRunner] = None
    ):
        if osutils is None:
            osutils = OSUtils()
        if uv_runner is None:
            uv_runner = UvRunner(osutils=osutils)

        self._osutils = osutils
        self._uv_runner = uv_runner
        self.runtime = runtime

    def build_dependencies(
        self,
        artifacts_dir_path: str,
        scratch_dir_path: str,
        manifest_path: str,
        architecture: str = X86_64,
        config: Optional[UvConfig] = None,
    ) -> None:
        """
        Build Python dependencies using UV.

        Args:
            artifacts_dir_path: Directory to write dependencies
            scratch_dir_path: Temporary directory for build operations
            manifest_path: Path to dependency manifest file
            architecture: Target architecture (X86_64 or ARM64)
            config: UV configuration options
        """
        LOG.info("Building Python dependencies using UV")
        LOG.info("Manifest file: %s", manifest_path)
        LOG.info("Target architecture: %s", architecture)
        LOG.info("Using scratch directory: %s", scratch_dir_path)

        if config is None:
            config = UvConfig()

        # Configure UV to use scratch directory for cache if not already set
        if not config.cache_dir:
            uv_cache_dir = os.path.join(scratch_dir_path, "uv-cache")
            # Use exist_ok equivalent for osutils
            if not os.path.exists(uv_cache_dir):
                self._osutils.makedirs(uv_cache_dir)
            config.cache_dir = uv_cache_dir
            LOG.debug("Configured UV cache directory: %s", uv_cache_dir)

        # Determine Python version from runtime
        python_version = self._extract_python_version(self.runtime)

        # Determine manifest type and build accordingly
        manifest_name = os.path.basename(manifest_path)

        try:
            # Get the appropriate handler for this manifest
            handler = self._get_manifest_handler(manifest_name)

            # Execute the handler
            handler(manifest_path, artifacts_dir_path, scratch_dir_path, python_version, architecture, config)

        except Exception as e:
            LOG.error("Failed to build dependencies: %s", str(e))
            raise

    def _get_manifest_handler(self, manifest_name: str):
        """Get the appropriate handler function for a manifest file."""
        # Exact match handlers for ACTUAL manifests
        exact_handlers = {
            "pyproject.toml": self._handle_pyproject_build,
        }

        # Check for exact match first
        if manifest_name in exact_handlers:
            return exact_handlers[manifest_name]

        # Check for requirements file pattern
        if self._is_requirements_file(manifest_name):
            return self._build_from_requirements

        # Generic unsupported file - covers uv.lock and everything else
        raise UvBuildError(reason=f"Unsupported manifest file: {manifest_name}")

    def _handle_pyproject_build(
        self,
        manifest_path: str,
        target_dir: str,
        scratch_dir: str,
        python_version: str,
        architecture: str,
        config: UvConfig,
    ) -> None:
        """
        Smart pyproject.toml handler that checks for uv.lock.

        If uv.lock exists alongside pyproject.toml, use lock-based build for more precise dependency resolution.
        Otherwise, use standard pyproject.toml build.
        """
        manifest_dir = os.path.dirname(manifest_path)
        uv_lock_path = os.path.join(manifest_dir, "uv.lock")

        if os.path.exists(uv_lock_path):
            LOG.info("Found uv.lock alongside pyproject.toml - using lock-based build for precise dependencies")
            # Use lock file for more precise builds
            self._build_from_lock_file(uv_lock_path, target_dir, scratch_dir, python_version, architecture, config)
        else:
            # Standard pyproject.toml build
            self._build_from_pyproject(manifest_path, target_dir, scratch_dir, python_version, architecture, config)

    def _is_requirements_file(self, filename: str) -> bool:
        """
        Check if a filename represents a valid requirements file.

        Follows Python ecosystem conventions:
        - requirements.txt (standard)
        - requirements-*.txt (environment-specific: dev, test, prod, etc.)
        """
        if filename == "requirements.txt":
            return True

        # Allow environment-specific requirements files like requirements-dev.txt
        # Must have at least one character after the dash and before .txt
        if (
            filename.startswith("requirements-")
            and filename.endswith(".txt")
            and len(filename) > len("requirements-.txt")
        ):
            return True

        return False

    def _build_from_lock_file(
        self,
        lock_path: str,
        target_dir: str,
        scratch_dir: str,
        python_version: str,
        architecture: str,
        config: UvConfig,
    ) -> None:
        """Build dependencies from uv.lock file."""
        LOG.info("Building from UV lock file")

        try:
            # For uv sync, we need the project directory (where pyproject.toml and uv.lock are)
            # uv sync automatically finds both files in the working directory
            project_dir = os.path.dirname(lock_path)

            self._uv_runner.sync_dependencies(
                project_dir=project_dir,  # Pass project directory instead of lock path
                target_dir=target_dir,
                scratch_dir=scratch_dir,
                config=config,
                python_version=python_version,
                platform="linux",
                architecture=architecture,
            )
        except Exception as e:
            raise LockFileError(reason=str(e))

    def _build_from_pyproject(
        self,
        pyproject_path: str,
        target_dir: str,
        scratch_dir: str,
        python_version: str,
        architecture: str,
        config: UvConfig,
    ) -> None:
        """Build dependencies from pyproject.toml file using UV's native workflow."""
        LOG.info("Building from pyproject.toml using UV lock and export")

        try:
            # Use UV's native workflow: lock -> export -> install
            temp_requirements = self._export_pyproject_to_requirements(pyproject_path, scratch_dir, python_version)

            if temp_requirements:
                self._uv_runner.install_requirements(
                    requirements_path=temp_requirements,
                    target_dir=target_dir,
                    scratch_dir=scratch_dir,
                    config=config,
                    python_version=python_version,
                    platform="linux",
                    architecture=architecture,
                )
            else:
                LOG.info("No dependencies found in pyproject.toml")

        except Exception as e:
            raise UvBuildError(reason=f"Failed to build from pyproject.toml: {str(e)}")

    def _export_pyproject_to_requirements(
        self, pyproject_path: str, scratch_dir: str, python_version: str
    ) -> Optional[str]:
        """Use UV's native lock and export to convert pyproject.toml to requirements.txt."""
        project_dir = os.path.dirname(pyproject_path)

        try:
            # Step 1: Create lock file using UV
            LOG.debug("Creating lock file from pyproject.toml")
            lock_args = ["lock", "--no-progress"]

            if python_version:
                lock_args.extend(["--python", python_version])

            rc, stdout, stderr = self._uv_runner._uv.run_uv_command(lock_args, cwd=project_dir)

            if rc != 0:
                LOG.warning(f"UV lock failed: {stderr}")
                return None

            # Step 2: Export lock file to requirements.txt format
            LOG.debug("Exporting lock file to requirements.txt format")
            temp_requirements = os.path.join(scratch_dir, "exported_requirements.txt")

            export_args = [
                "export",
                "--format",
                "requirements.txt",
                "--no-emit-project",  # Don't include the project itself, only dependencies
                "--no-header",  # Skip comment header
                "--no-hashes",  # Skip hashes for cleaner output (optional)
                "--output-file",
                temp_requirements,
            ]

            rc, stdout, stderr = self._uv_runner._uv.run_uv_command(export_args, cwd=project_dir)

            if rc != 0:
                LOG.warning(f"UV export failed: {stderr}")
                return None

            # Verify the requirements file was created and has content
            if os.path.exists(temp_requirements) and os.path.getsize(temp_requirements) > 0:
                LOG.debug(f"Successfully exported dependencies to {temp_requirements}")
                return temp_requirements
            else:
                LOG.info("No dependencies to export from pyproject.toml")
                return None

        except Exception as e:
            LOG.warning(f"Failed to export pyproject.toml using UV native workflow: {e}")
            return None

    def _build_from_requirements(
        self,
        requirements_path: str,
        target_dir: str,
        scratch_dir: str,
        python_version: str,
        architecture: str,
        config: UvConfig,
    ) -> None:
        """Build dependencies from requirements.txt file."""
        LOG.info("Building from requirements file")

        try:
            self._uv_runner.install_requirements(
                requirements_path=requirements_path,
                target_dir=target_dir,
                scratch_dir=scratch_dir,
                config=config,
                python_version=python_version,
                platform="linux",
                architecture=architecture,
            )
        except Exception as e:
            raise UvBuildError(reason=f"Failed to build from requirements: {str(e)}")

    def _extract_python_version(self, runtime: str) -> str:
        """Extract Python version from runtime string."""
        if not runtime:
            raise UvBuildError(reason="Runtime is required but was not provided")

        # Extract version from runtime like "python3.9" -> "3.9"
        if runtime.startswith("python"):
            return runtime.replace("python", "")

        return runtime
