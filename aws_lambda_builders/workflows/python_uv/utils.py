"""
Commonly used utilities for Python UV workflow
"""

import logging
import os
import shutil
import subprocess
from typing import List, Optional

from aws_lambda_builders.workflows.python_pip.utils import OSUtils as BaseOSUtils

LOG = logging.getLogger(__name__)

EXPERIMENTAL_FLAG_BUILD_PERFORMANCE = "experimentalBuildPerformance"


class OSUtils(BaseOSUtils):
    """Extended OS utilities for UV workflow."""

    def which(self, executable):
        """Find executable in PATH."""
        return shutil.which(executable)

    def run_subprocess(self, cmd, cwd=None, env=None):
        """Run subprocess and return result."""
        if env is None:
            env = self.original_environ()

        try:
            result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", str(e)


def detect_uv_manifest(source_dir: str) -> Optional[str]:
    """
    Detect UV-compatible manifest files in order of preference.

    Note: uv.lock is NOT a manifest - it's a lock file that accompanies pyproject.toml.
    UV workflows support these manifest types:
    1. pyproject.toml - may have accompanying uv.lock
    2. requirements.txt (or requirements-prod.txt) - traditional pip-style manifests

    A pyproject.toml wins when it is the uv project: it has a uv.lock beside it or declares
    non-empty dependencies in its [project] table. Otherwise it may only hold metadata or tool settings,
    so requirements.txt is used when present. Development and test requirements files are never
    used, because their contents do not belong in a Lambda deployment package.

    Args:
        source_dir: Directory to search for manifest files

    Returns:
        Path to the detected manifest file, or None if not found
    """
    pyproject_path = os.path.join(source_dir, "pyproject.toml")
    has_pyproject = os.path.isfile(pyproject_path)
    if has_pyproject and _is_uv_project(source_dir, pyproject_path):
        return pyproject_path

    for requirements_file in ("requirements.txt", "requirements-prod.txt"):
        requirements_path = os.path.join(source_dir, requirements_file)
        if os.path.isfile(requirements_path):
            return requirements_path

    if has_pyproject:
        return pyproject_path

    return None


def _is_uv_project(source_dir: str, pyproject_path: str) -> bool:
    """Whether pyproject.toml, not a requirements file, describes this function's dependencies."""
    if os.path.isfile(os.path.join(source_dir, "uv.lock")):
        return True

    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            LOG.debug("No TOML parser available; preferring requirements files over %s", pyproject_path)
            return False

    try:
        with open(pyproject_path, "rb") as pyproject_file:
            project = tomllib.load(pyproject_file).get("project")
    except (OSError, ValueError) as error:  # tomllib.TOMLDecodeError subclasses ValueError
        LOG.debug("Could not read %s: %s", pyproject_path, error)
        return False

    if not isinstance(project, dict):
        return False
    # Empty (uv init) or dynamic dependencies usually live in requirements.txt, so let it win.
    return bool(project.get("dependencies"))


def get_uv_version(uv_executable: str, osutils: OSUtils) -> Optional[str]:
    """
    Get UV version from the executable.

    Args:
        uv_executable: Path to UV executable
        osutils: OS utilities instance

    Returns:
        UV version string or None if unable to determine
    """
    try:
        rc, stdout, stderr = osutils.run_subprocess([uv_executable, "--version"])
        if rc == 0 and stdout:
            # UV version output format: "uv 0.1.0"
            parts = stdout.strip().split()
            min_parts_for_version = 2
            if len(parts) >= min_parts_for_version:
                return parts[1]
    except Exception:
        pass

    return None


class UvConfig:
    """Configuration class for UV operations."""

    def __init__(
        self,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        cache_dir: Optional[str] = None,
        no_cache: bool = False,
        prerelease: str = "disallow",
        resolution: str = "highest",
        compile_bytecode: bool = True,
        exclude_newer: Optional[str] = None,
        generate_hashes: bool = False,
    ):
        self.index_url = index_url
        self.extra_index_urls = extra_index_urls or []
        self.cache_dir = cache_dir
        self.no_cache = no_cache
        self.prerelease = prerelease
        self.resolution = resolution
        self.compile_bytecode = compile_bytecode
        self.exclude_newer = exclude_newer
        self.generate_hashes = generate_hashes

    def to_uv_args(self) -> List[str]:
        """Convert configuration to UV command line arguments."""
        args = []

        if self.index_url:
            args.extend(["--index-url", self.index_url])

        for extra_url in self.extra_index_urls:
            args.extend(["--extra-index-url", extra_url])

        if self.cache_dir:
            args.extend(["--cache-dir", self.cache_dir])

        if self.no_cache:
            args.append("--no-cache")

        if self.prerelease != "disallow":
            args.extend(["--prerelease", self.prerelease])

        if self.resolution != "highest":
            args.extend(["--resolution", self.resolution])

        if self.exclude_newer:
            args.extend(["--exclude-newer", self.exclude_newer])

        if self.generate_hashes:
            args.append("--generate-hashes")

        return args
