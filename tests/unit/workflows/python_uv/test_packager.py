from unittest import TestCase
from unittest.mock import Mock, patch

from aws_lambda_builders.architecture import X86_64, ARM64
from aws_lambda_builders.workflows.python_uv.packager import SubprocessUv, UvRunner, PythonUvDependencyBuilder
from aws_lambda_builders.workflows.python_uv.exceptions import MissingUvError, UvInstallationError, UvBuildError
from aws_lambda_builders.workflows.python_uv.utils import UvConfig


class TestSubprocessUv(TestCase):
    @patch("aws_lambda_builders.workflows.python_uv.packager.OSUtils")
    def test_subprocess_uv_init_success(self, mock_osutils_class):
        mock_osutils = Mock()
        mock_osutils.which.return_value = "/usr/bin/uv"
        mock_osutils_class.return_value = mock_osutils

        subprocess_uv = SubprocessUv()
        self.assertEqual(subprocess_uv.uv_executable, "/usr/bin/uv")

    @patch("aws_lambda_builders.workflows.python_uv.packager.OSUtils")
    def test_subprocess_uv_init_missing_uv(self, mock_osutils_class):
        mock_osutils = Mock()
        mock_osutils.which.return_value = None
        mock_osutils_class.return_value = mock_osutils

        with self.assertRaises(MissingUvError):
            SubprocessUv()

    @patch("aws_lambda_builders.workflows.python_uv.packager.OSUtils")
    def test_run_uv_command_success(self, mock_osutils_class):
        mock_osutils = Mock()
        mock_osutils.which.return_value = "/usr/bin/uv"
        mock_osutils.run_subprocess.return_value = (0, "success", "")
        mock_osutils_class.return_value = mock_osutils

        subprocess_uv = SubprocessUv()
        rc, stdout, stderr = subprocess_uv.run_uv_command(["--version"])

        self.assertEqual(rc, 0)
        self.assertEqual(stdout, "success")
        self.assertEqual(stderr, "")
        mock_osutils.run_subprocess.assert_called_once_with(["/usr/bin/uv", "--version"], cwd=None, env=None)


class TestUvRunner(TestCase):
    def setUp(self):
        self.mock_subprocess_uv = Mock()
        self.mock_subprocess_uv.uv_executable = "/usr/bin/uv"
        self.mock_osutils = Mock()
        self.uv_runner = UvRunner(uv_subprocess=self.mock_subprocess_uv, osutils=self.mock_osutils)

    @patch("aws_lambda_builders.workflows.python_uv.packager.get_uv_version")
    def test_uv_version_property(self, mock_get_version):
        mock_get_version.return_value = "0.6.16"

        version = self.uv_runner.uv_version
        self.assertEqual(version, "0.6.16")
        mock_get_version.assert_called_once_with("/usr/bin/uv", self.mock_osutils)

    def test_sync_dependencies_success(self):
        self.mock_subprocess_uv.run_uv_command.return_value = (0, "success", "")

        self.uv_runner.sync_dependencies(
            manifest_path="/path/to/pyproject.toml",
            target_dir="/target",
            scratch_dir="/scratch",
            python_version="3.9",
            platform="linux",
            architecture=X86_64,
        )

        # Verify UV sync command was called with correct arguments
        args_called = self.mock_subprocess_uv.run_uv_command.call_args[0][0]
        self.assertIn("sync", args_called)
        self.assertIn("--python", args_called)
        self.assertIn("3.9", args_called)
        # Note: UV sync doesn't support --target, it syncs to the project environment

    def test_sync_dependencies_failure(self):
        self.mock_subprocess_uv.run_uv_command.return_value = (1, "", "error message")

        with self.assertRaises(UvInstallationError):
            self.uv_runner.sync_dependencies(
                manifest_path="/path/to/pyproject.toml", target_dir="/target", scratch_dir="/scratch"
            )

    def test_install_requirements_success(self):
        self.mock_subprocess_uv.run_uv_command.return_value = (0, "success", "")

        self.uv_runner.install_requirements(
            requirements_path="/path/to/requirements.txt",
            target_dir="/target",
            scratch_dir="/scratch",
            python_version="3.9",
            platform="linux",
            architecture=X86_64,
        )

        # Verify UV pip install command was called
        args_called = self.mock_subprocess_uv.run_uv_command.call_args[0][0]
        self.assertIn("pip", args_called)
        self.assertIn("install", args_called)
        self.assertIn("-r", args_called)
        self.assertIn("/path/to/requirements.txt", args_called)

    def test_install_requirements_failure(self):
        self.mock_subprocess_uv.run_uv_command.return_value = (1, "", "error message")

        with self.assertRaises(UvInstallationError):
            self.uv_runner.install_requirements(
                requirements_path="/path/to/requirements.txt", target_dir="/target", scratch_dir="/scratch"
            )


class TestPythonUvDependencyBuilder(TestCase):
    def setUp(self):
        self.mock_osutils = Mock()
        self.mock_uv_runner = Mock()
        self.builder = PythonUvDependencyBuilder(
            osutils=self.mock_osutils, runtime="python3.9", uv_runner=self.mock_uv_runner
        )

    def test_extract_python_version(self):
        self.assertEqual(self.builder._extract_python_version("python3.9"), "3.9")
        self.assertEqual(self.builder._extract_python_version("python3.11"), "3.11")
        self.assertEqual(self.builder._extract_python_version("3.10"), "3.10")

        # Runtime is required - should raise error when None
        with self.assertRaises(UvBuildError) as context:
            self.builder._extract_python_version(None)
        self.assertIn("Runtime is required", str(context.exception))

        # Empty string should also raise error
        with self.assertRaises(UvBuildError) as context:
            self.builder._extract_python_version("")
        self.assertIn("Runtime is required", str(context.exception))

    def test_build_from_lock_file(self):
        self.builder._build_from_lock_file(
            lock_path="/path/to/uv.lock",
            target_dir="/target",
            scratch_dir="/scratch",
            python_version="3.9",
            architecture=X86_64,
            config=UvConfig(),
        )

        self.mock_uv_runner.sync_dependencies.assert_called_once()

    def test_build_from_requirements(self):
        self.builder._build_from_requirements(
            requirements_path="/path/to/requirements.txt",
            target_dir="/target",
            scratch_dir="/scratch",
            python_version="3.9",
            architecture=X86_64,
            config=UvConfig(),
        )

        self.mock_uv_runner.install_requirements.assert_called_once()

    def test_build_dependencies_with_requirements_txt(self):
        with patch("os.path.basename", return_value="requirements.txt"):
            self.builder.build_dependencies(
                artifacts_dir_path="/artifacts",
                scratch_dir_path="/scratch",
                manifest_path="/path/to/requirements.txt",
                architecture=X86_64,
            )

        self.mock_uv_runner.install_requirements.assert_called_once()

    def test_build_dependencies_with_uv_lock_standalone_fails(self):
        """Test that uv.lock as standalone manifest fails (requires pyproject.toml)."""
        with patch("os.path.basename", return_value="uv.lock"):
            with self.assertRaises(UvBuildError) as context:
                self.builder.build_dependencies(
                    artifacts_dir_path="/artifacts",
                    scratch_dir_path="/scratch",
                    manifest_path="/path/to/uv.lock",
                    architecture=X86_64,
                )

            self.assertIn("Unsupported manifest file: uv.lock", str(context.exception))

        # Should not call any UV operations for unsupported manifest
        self.mock_uv_runner.sync_dependencies.assert_not_called()
        self.mock_uv_runner.install_requirements.assert_not_called()

    def test_build_dependencies_pyproject_with_uv_lock(self):
        """Test that pyproject.toml with uv.lock present uses lock-based build."""
        with patch("os.path.basename", return_value="pyproject.toml"), patch(
            "os.path.dirname", return_value="/path/to"
        ), patch("os.path.exists") as mock_exists:

            # Mock that uv.lock exists alongside pyproject.toml
            mock_exists.return_value = True

            self.builder.build_dependencies(
                artifacts_dir_path="/artifacts",
                scratch_dir_path="/scratch",
                manifest_path="/path/to/pyproject.toml",
                architecture=X86_64,
            )

        # Should use sync_dependencies (lock-based build)
        self.mock_uv_runner.sync_dependencies.assert_called_once()
        self.mock_uv_runner.install_requirements.assert_not_called()

        # Verify it checked for uv.lock in the right location
        mock_exists.assert_called_with("/path/to/uv.lock")

    def test_build_dependencies_pyproject_without_uv_lock(self):
        """Test that pyproject.toml without uv.lock uses standard pyproject build."""
        with patch("os.path.basename", return_value="pyproject.toml"), patch(
            "os.path.dirname", return_value="/path/to"
        ), patch("os.path.exists") as mock_exists, patch.object(
            self.builder, "_export_pyproject_to_requirements", return_value="/temp/requirements.txt"
        ):

            # Mock that uv.lock does NOT exist alongside pyproject.toml
            mock_exists.return_value = False

            self.builder.build_dependencies(
                artifacts_dir_path="/artifacts",
                scratch_dir_path="/scratch",
                manifest_path="/path/to/pyproject.toml",
                architecture=X86_64,
            )

        # Should use install_requirements (standard pyproject build)
        self.mock_uv_runner.install_requirements.assert_called_once()
        self.mock_uv_runner.sync_dependencies.assert_not_called()

        # Verify it checked for uv.lock in the right location
        mock_exists.assert_called_with("/path/to/uv.lock")

    def test_build_dependencies_configures_cache_dir(self):
        """Test that build_dependencies properly configures UV cache directory in scratch_dir."""
        with patch("os.path.basename", return_value="requirements.txt"):
            self.builder.build_dependencies(
                artifacts_dir_path="/artifacts",
                scratch_dir_path="/scratch",
                manifest_path="/path/to/requirements.txt",
                architecture=X86_64,
            )

        # Verify that install_requirements was called with scratch_dir
        call_args = self.mock_uv_runner.install_requirements.call_args
        self.assertEqual(call_args[1]["scratch_dir"], "/scratch")

        # Verify that makedirs was called to create cache directory
        self.mock_osutils.makedirs.assert_called()

    def test_build_dependencies_respects_existing_cache_dir(self):
        """Test that existing cache_dir in config is respected."""
        from aws_lambda_builders.workflows.python_uv.utils import UvConfig

        config = UvConfig(cache_dir="/custom/cache")

        with patch("os.path.basename", return_value="requirements.txt"):
            self.builder.build_dependencies(
                artifacts_dir_path="/artifacts",
                scratch_dir_path="/scratch",
                manifest_path="/path/to/requirements.txt",
                architecture=X86_64,
                config=config,
            )

        # Verify that the custom cache directory is preserved
        call_args = self.mock_uv_runner.install_requirements.call_args
        passed_config = call_args[1]["config"]
        self.assertEqual(passed_config.cache_dir, "/custom/cache")

    def test_is_requirements_file_standard_names(self):
        # Test standard requirements file name
        self.assertTrue(self.builder._is_requirements_file("requirements.txt"))

    def test_is_requirements_file_environment_specific(self):
        # Test environment-specific requirements files
        self.assertTrue(self.builder._is_requirements_file("requirements-dev.txt"))
        self.assertTrue(self.builder._is_requirements_file("requirements-test.txt"))
        self.assertTrue(self.builder._is_requirements_file("requirements-prod.txt"))
        self.assertTrue(self.builder._is_requirements_file("requirements-staging.txt"))

    def test_is_requirements_file_invalid_names(self):
        # Test invalid requirements file names
        self.assertFalse(self.builder._is_requirements_file("requirements"))
        self.assertFalse(self.builder._is_requirements_file("requirements.in"))
        self.assertFalse(self.builder._is_requirements_file("requirements.py"))
        self.assertFalse(self.builder._is_requirements_file("my-requirements.txt"))
        self.assertFalse(self.builder._is_requirements_file("requirements.txt.bak"))
        self.assertFalse(self.builder._is_requirements_file("requirements-"))
        self.assertFalse(self.builder._is_requirements_file("requirements-.txt"))
