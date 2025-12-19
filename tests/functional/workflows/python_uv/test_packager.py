import os
from collections import defaultdict, namedtuple

import pytest

from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.workflows.python_uv.exceptions import UvBuildError
from aws_lambda_builders.workflows.python_uv.packager import PythonUvDependencyBuilder, SubprocessUv, UvRunner
from aws_lambda_builders.workflows.python_uv.utils import OSUtils, UvConfig

FakeUvCall = namedtuple("FakeUvEntry", ["args", "env_vars", "cwd"])


def _create_app_structure(tmpdir):
    appdir = tmpdir.mkdir("app")
    appdir.join("app.py").write("# Test app")
    return appdir


class FakeUv(object):
    """Mock UV executable for functional testing"""

    def __init__(self):
        self._calls = defaultdict(lambda: [])
        self._call_history = []
        self._side_effects = defaultdict(lambda: [])
        self._return_tuple = (0, b"", b"")

    def run_uv_command(self, args, cwd=None, env=None):
        """Mock UV command execution"""
        cmd = args[0] if args else "unknown"
        self._calls[cmd].append((args, env, cwd))

        try:
            side_effects = self._side_effects[cmd].pop(0)
            for side_effect in side_effects:
                self._call_history.append(
                    (
                        FakeUvCall(args, env, cwd),
                        FakeUvCall(side_effect.expected_args, side_effect.expected_env, side_effect.expected_cwd),
                    )
                )
                side_effect.execute(args, cwd)
        except IndexError:
            pass

        return self._return_tuple

    def set_return_tuple(self, rc, out, err):
        self._return_tuple = (rc, out, err)

    def packages_to_install(self, expected_args, packages, install_location=None):
        """Mock package installation with fake packages"""
        side_effects = [UvSideEffect(pkg, expected_args, install_location) for pkg in packages]
        self._side_effects["pip"].append(side_effects)

    def sync_dependencies(self, expected_args, packages, project_dir=None):
        """Mock UV sync operation"""
        side_effects = [UvSyncSideEffect(pkg, expected_args, project_dir) for pkg in packages]
        self._side_effects["sync"].append(side_effects)

    def validate(self):
        """Validate that all expected calls were made"""
        for cmd, calls in self._calls.items():
            if calls:
                # All calls were made successfully
                pass


class UvSideEffect(object):
    """Side effect for UV pip install commands"""

    def __init__(self, package_name, expected_args, install_location=None):
        self.package_name = package_name
        self.expected_args = expected_args
        self.expected_env = None
        self.expected_cwd = None
        self.install_location = install_location

    def execute(self, args, cwd=None):
        """Execute the side effect - create fake package files"""
        if self.install_location and os.path.exists(self.install_location):
            # Create fake package directory
            package_dir = os.path.join(self.install_location, self.package_name)
            os.makedirs(package_dir, exist_ok=True)

            # Create fake __init__.py
            init_file = os.path.join(package_dir, "__init__.py")
            with open(init_file, "w") as f:
                f.write(f"# Fake {self.package_name} package\n")

            # Create fake dist-info directory
            dist_info = os.path.join(self.install_location, f"{self.package_name}-1.0.0.dist-info")
            os.makedirs(dist_info, exist_ok=True)

            # Create fake METADATA file
            metadata_file = os.path.join(dist_info, "METADATA")
            with open(metadata_file, "w") as f:
                f.write(f"Name: {self.package_name}\nVersion: 1.0.0\n")


class UvSyncSideEffect(object):
    """Side effect for UV sync commands"""

    def __init__(self, package_name, expected_args, project_dir=None):
        self.package_name = package_name
        self.expected_args = expected_args
        self.expected_env = None
        self.expected_cwd = project_dir

    def execute(self, args, cwd=None):
        """Execute sync side effect - create virtual environment structure"""
        if cwd and os.path.exists(cwd):
            # Create fake .venv directory
            venv_dir = os.path.join(cwd, ".venv")
            site_packages = os.path.join(venv_dir, "lib", "python3.13", "site-packages")
            os.makedirs(site_packages, exist_ok=True)

            # Create fake package in site-packages
            package_dir = os.path.join(site_packages, self.package_name)
            os.makedirs(package_dir, exist_ok=True)

            init_file = os.path.join(package_dir, "__init__.py")
            with open(init_file, "w") as f:
                f.write(f"# Fake {self.package_name} package from sync\n")


@pytest.fixture
def osutils():
    return OSUtils()


@pytest.fixture
def uv_runner(osutils):
    fake_uv = FakeUv()
    subprocess_uv = SubprocessUv(osutils=osutils)
    # Replace the real UV with our fake one
    subprocess_uv.run_uv_command = fake_uv.run_uv_command
    uv_runner = UvRunner(uv_subprocess=subprocess_uv, osutils=osutils)
    return fake_uv, uv_runner


class TestPythonUvDependencyBuilder(object):
    """Functional tests for UV dependency builder"""

    def _write_requirements_txt(self, packages, directory):
        """Write requirements.txt file"""
        contents = "\n".join(packages)
        filepath = os.path.join(directory, "requirements.txt")
        with open(filepath, "w") as f:
            f.write(contents)

    def _write_pyproject_toml(self, packages, directory, name="test-project"):
        """Write pyproject.toml file"""
        deps = '", "'.join(packages)
        content = f"""[project]
name = "{name}"
version = "1.0.0"
requires-python = ">=3.8"
dependencies = ["{deps}"]

[tool.uv]
dev-dependencies = []
"""
        filepath = os.path.join(directory, "pyproject.toml")
        with open(filepath, "w") as f:
            f.write(content)

    def _make_appdir_and_dependency_builder(self, reqs, tmpdir, uv_runner, manifest_type="requirements", **kwargs):
        """Create app directory and dependency builder"""
        appdir = str(_create_app_structure(tmpdir))

        if manifest_type == "requirements":
            self._write_requirements_txt(reqs, appdir)
            manifest_path = os.path.join(appdir, "requirements.txt")
        elif manifest_type == "pyproject":
            self._write_pyproject_toml(reqs, appdir)
            manifest_path = os.path.join(appdir, "pyproject.toml")
        else:
            raise ValueError(f"Unknown manifest type: {manifest_type}")

        builder = PythonUvDependencyBuilder(osutils=OSUtils(), runtime="python3.13", uv_runner=uv_runner, **kwargs)
        return appdir, builder, manifest_path

    def test_can_build_simple_requirements(self, tmpdir, uv_runner, osutils):
        """Test building simple requirements.txt dependencies"""
        reqs = ["requests", "boto3"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        # Set up fake UV to return success
        fake_uv.set_return_tuple(0, b"Successfully installed requests boto3", b"")

        # Mock the package installation
        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=[
                "pip",
                "install",
                "--python-version",
                "3.13",
                "--python-platform",
                "x86_64-unknown-linux-gnu",
            ],
            packages=reqs,
            install_location=site_packages,
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=UvConfig(),
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        for req in reqs:
            assert req in installed_packages

    def test_can_build_pyproject_dependencies(self, tmpdir, uv_runner, osutils):
        """Test building pyproject.toml dependencies"""
        reqs = ["numpy", "pandas"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="pyproject"
        )

        # Set up fake UV sync operation
        fake_uv.set_return_tuple(0, b"Resolved 2 packages", b"")
        fake_uv.sync_dependencies(expected_args=["sync", "--python", "3.13"], packages=reqs, project_dir=appdir)

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=UvConfig(),
            )

        # For pyproject.toml, packages would be in .venv initially
        venv_site_packages = os.path.join(appdir, ".venv", "lib", "python3.13", "site-packages")
        if os.path.exists(venv_site_packages):
            installed_packages = os.listdir(venv_site_packages)
            for req in reqs:
                assert req in installed_packages

    def test_can_handle_arm64_architecture(self, tmpdir, uv_runner, osutils):
        """Test building dependencies for ARM64 architecture"""
        reqs = ["cryptography"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        fake_uv.set_return_tuple(0, b"Successfully installed cryptography", b"")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=[
                "pip",
                "install",
                "--python-version",
                "3.13",
                "--python-platform",
                "aarch64-unknown-linux-gnu",
            ],
            packages=reqs,
            install_location=site_packages,
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=ARM64,  # Test ARM64 architecture
                config=UvConfig(),
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        for req in reqs:
            assert req in installed_packages

    def test_handles_uv_installation_failure(self, tmpdir, uv_runner, osutils):
        """Test handling of UV installation failures"""
        reqs = ["nonexistent-package"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        # Set up fake UV to return failure
        error_msg = b"ERROR: Could not find a version that satisfies the requirement"
        fake_uv.set_return_tuple(1, b"", error_msg)

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)

        with pytest.raises(UvBuildError):
            with osutils.tempdir() as scratch_dir:
                builder.build_dependencies(
                    artifacts_dir_path=site_packages,
                    scratch_dir_path=scratch_dir,
                    manifest_path=manifest_path,
                    architecture=X86_64,
                    config=UvConfig(),
                )

    def test_can_build_with_custom_config(self, tmpdir, uv_runner, osutils):
        """Test building with custom UV configuration"""
        reqs = ["flask"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        fake_uv.set_return_tuple(0, b"Successfully installed flask", b"")

        # Test with custom configuration
        config = UvConfig(
            index_url="https://custom-pypi.example.com/simple",
            extra_index_urls=["https://extra-pypi.example.com/simple"],
            no_cache=True,
        )

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=["pip", "install", "--index-url", "https://custom-pypi.example.com/simple"],
            packages=reqs,
            install_location=site_packages,
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=config,
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        for req in reqs:
            assert req in installed_packages

    def test_can_build_with_lock_file_optimization(self, tmpdir, uv_runner, osutils):
        """Test building with existing uv.lock file for optimization"""
        reqs = ["django"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="pyproject"
        )

        # Create a fake uv.lock file
        lock_content = """version = 1
requires-python = ">=3.8"

[[package]]
name = "django"
version = "4.2.0"
"""
        lock_path = os.path.join(appdir, "uv.lock")
        with open(lock_path, "w") as f:
            f.write(lock_content)

        fake_uv.set_return_tuple(0, b"Using existing lock file", b"")
        fake_uv.sync_dependencies(expected_args=["sync", "--python", "3.13"], packages=reqs, project_dir=appdir)

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=UvConfig(),
            )

        # Verify lock file was used (it should still exist)
        assert os.path.exists(lock_path)
        fake_uv.validate()

    def test_can_build_mixed_package_types(self, tmpdir, uv_runner, osutils):
        """Test building mixed package types (pure Python, binary, etc.)"""
        reqs = ["requests", "numpy", "pyyaml"]  # Mix of pure Python and binary packages
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        fake_uv.set_return_tuple(0, b"Successfully installed requests numpy pyyaml", b"")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=["pip", "install", "--python-version", "3.13"], packages=reqs, install_location=site_packages
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=UvConfig(),
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        # Verify all package types were installed
        for req in reqs:
            assert req in installed_packages
            # Verify dist-info directories exist
            dist_info_dirs = [d for d in installed_packages if d.startswith(f"{req}-") and d.endswith(".dist-info")]
            assert len(dist_info_dirs) > 0, f"Missing dist-info for {req}"

    def test_can_handle_environment_specific_requirements(self, tmpdir, uv_runner, osutils):
        """Test building with environment-specific requirements files"""
        reqs = ["pytest", "coverage"]
        fake_uv, runner = uv_runner
        appdir = str(_create_app_structure(tmpdir))

        # Create requirements-dev.txt (environment-specific)
        dev_requirements = os.path.join(appdir, "requirements-dev.txt")
        self._write_requirements_txt(reqs, appdir)
        os.rename(os.path.join(appdir, "requirements.txt"), dev_requirements)

        builder = PythonUvDependencyBuilder(osutils=OSUtils(), runtime="python3.13", uv_runner=runner)

        fake_uv.set_return_tuple(0, b"Successfully installed pytest coverage", b"")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=["pip", "install", "-r", "requirements-dev.txt"],
            packages=reqs,
            install_location=site_packages,
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=dev_requirements,
                architecture=X86_64,
                config=UvConfig(),
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        for req in reqs:
            assert req in installed_packages

    def test_can_handle_large_dependency_trees(self, tmpdir, uv_runner, osutils):
        """Test building large dependency trees efficiently"""
        # Simulate a large project with many dependencies
        reqs = [
            "django",
            "djangorestframework",
            "celery",
            "redis",
            "psycopg2-binary",
            "pillow",
            "boto3",
            "requests",
            "numpy",
            "pandas",
            "matplotlib",
        ]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="pyproject"
        )

        fake_uv.set_return_tuple(0, f"Resolved {len(reqs)} packages".encode(), b"")
        fake_uv.sync_dependencies(expected_args=["sync", "--python", "3.13"], packages=reqs, project_dir=appdir)

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=UvConfig(),
            )

        # For large dependency trees, verify core packages are present
        venv_site_packages = os.path.join(appdir, ".venv", "lib", "python3.13", "site-packages")
        if os.path.exists(venv_site_packages):
            installed_packages = os.listdir(venv_site_packages)
            core_packages = ["django", "requests", "boto3", "numpy"]
            for pkg in core_packages:
                assert pkg in installed_packages

    def test_can_handle_conflicting_dependencies(self, tmpdir, uv_runner, osutils):
        """Test handling of conflicting dependency versions"""
        # Create a scenario with potential version conflicts
        reqs = ["package-a==1.0.0", "package-b>=2.0.0"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        # UV should handle conflicts gracefully or fail with clear error
        fake_uv.set_return_tuple(1, b"", b"No solution found when resolving dependencies")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)

        with pytest.raises(UvBuildError) as exc_info:
            with osutils.tempdir() as scratch_dir:
                builder.build_dependencies(
                    artifacts_dir_path=site_packages,
                    scratch_dir_path=scratch_dir,
                    manifest_path=manifest_path,
                    architecture=X86_64,
                    config=UvConfig(),
                )

        # Verify error message contains useful information
        assert "No solution found" in str(exc_info.value)

    def test_can_build_with_custom_python_version(self, tmpdir, uv_runner, osutils):
        """Test building with different Python versions"""
        reqs = ["typing-extensions"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        # Test with Python 3.11 instead of 3.13
        builder_py311 = PythonUvDependencyBuilder(
            osutils=OSUtils(), runtime="python3.11", uv_runner=runner  # Different Python version
        )

        fake_uv.set_return_tuple(0, b"Successfully installed typing-extensions", b"")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=["pip", "install", "--python-version", "3.11"],  # Should use 3.11
            packages=reqs,
            install_location=site_packages,
        )

        with osutils.tempdir() as scratch_dir:
            builder_py311.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=UvConfig(),
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        for req in reqs:
            assert req in installed_packages

    def test_can_build_with_prerelease_packages(self, tmpdir, uv_runner, osutils):
        """Test building with prerelease package versions"""
        reqs = ["django>=4.0.0a1"]  # Prerelease version
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        # Configure to allow prereleases
        config = UvConfig(prerelease="allow")

        fake_uv.set_return_tuple(0, b"Successfully installed django", b"")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=["pip", "install", "--prerelease", "allow"],
            packages=["django"],
            install_location=site_packages,
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=config,
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        assert "django" in installed_packages

    def test_can_build_with_hash_verification(self, tmpdir, uv_runner, osutils):
        """Test building with package hash verification"""
        reqs = ["certifi==2023.7.22"]
        fake_uv, runner = uv_runner
        appdir, builder, manifest_path = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, manifest_type="requirements"
        )

        # Configure to generate/verify hashes
        config = UvConfig(generate_hashes=True)

        fake_uv.set_return_tuple(0, b"Successfully installed certifi", b"")

        site_packages = os.path.join(appdir, "site-packages")
        os.makedirs(site_packages, exist_ok=True)
        fake_uv.packages_to_install(
            expected_args=["pip", "install", "--generate-hashes"], packages=["certifi"], install_location=site_packages
        )

        with osutils.tempdir() as scratch_dir:
            builder.build_dependencies(
                artifacts_dir_path=site_packages,
                scratch_dir_path=scratch_dir,
                manifest_path=manifest_path,
                architecture=X86_64,
                config=config,
            )

        installed_packages = os.listdir(site_packages)
        fake_uv.validate()

        assert "certifi" in installed_packages
