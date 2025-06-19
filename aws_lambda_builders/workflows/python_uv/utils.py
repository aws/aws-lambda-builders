"""
Commonly used utilities for Python UV workflow
"""

import os
import shutil
import subprocess
from typing import List, Optional

from aws_lambda_builders.workflows.python_pip.utils import OSUtils as BaseOSUtils

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
    1. pyproject.toml (preferred) - may have accompanying uv.lock
    2. requirements.txt and variants - traditional pip-style manifests

    Args:
        source_dir: Directory to search for manifest files

    Returns:
        Path to the detected manifest file, or None if not found
    """
    # Check for pyproject.toml first (preferred manifest)
    pyproject_path = os.path.join(source_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        return pyproject_path
    
    # Check for requirements.txt variants (in order of preference)
    requirements_variants = [
        "requirements.txt",
        "requirements-dev.txt", 
        "requirements-test.txt",
        "requirements-prod.txt"
    ]
    
    for requirements_file in requirements_variants:
        requirements_path = os.path.join(source_dir, requirements_file)
        if os.path.isfile(requirements_path):
            return requirements_path

    return None


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
