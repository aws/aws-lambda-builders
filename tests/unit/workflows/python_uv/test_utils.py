import os
import tempfile
from unittest import TestCase
from unittest.mock import Mock

from aws_lambda_builders.workflows.python_uv.utils import (
    OSUtils,
    UvConfig,
    detect_uv_manifest,
    get_uv_version,
)


class TestOSUtils(TestCase):
    def setUp(self):
        self.osutils = OSUtils()

    def test_which_existing_command(self):
        # Test with a command that should exist on most systems
        result = self.osutils.which("ls")
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(result))

    def test_which_nonexistent_command(self):
        result = self.osutils.which("nonexistent_command_12345")
        self.assertIsNone(result)

    def test_run_subprocess_success(self):
        rc, stdout, stderr = self.osutils.run_subprocess(["echo", "hello"])
        self.assertEqual(rc, 0)
        self.assertEqual(stdout.strip(), "hello")
        self.assertEqual(stderr, "")

    def test_run_subprocess_failure(self):
        rc, stdout, stderr = self.osutils.run_subprocess(["false"])
        self.assertEqual(rc, 1)


class TestDetectUvManifest(TestCase):
    def test_detect_uv_manifest_no_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = detect_uv_manifest(temp_dir)
            self.assertIsNone(result)

    def test_detect_uv_manifest_requirements_txt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            req_path = os.path.join(temp_dir, "requirements.txt")
            with open(req_path, "w") as f:
                f.write("requests==2.28.0\n")

            result = detect_uv_manifest(temp_dir)
            self.assertEqual(result, req_path)

    def test_detect_uv_manifest_pyproject_toml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject_path = os.path.join(temp_dir, "pyproject.toml")
            with open(pyproject_path, "w") as f:
                f.write("[project]\nname = 'test'\n")

            result = detect_uv_manifest(temp_dir)
            self.assertEqual(result, pyproject_path)

    def test_detect_uv_manifest_pyproject_priority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple manifest files
            pyproject_path = os.path.join(temp_dir, "pyproject.toml")
            req_path = os.path.join(temp_dir, "requirements.txt")

            with open(pyproject_path, "w") as f:
                f.write("[project]\nname = 'test'\n")
            with open(req_path, "w") as f:
                f.write("requests==2.28.0\n")

            result = detect_uv_manifest(temp_dir)
            # pyproject.toml should have priority over requirements.txt
            self.assertEqual(result, pyproject_path)

    def test_detect_uv_manifest_requirements_variants(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create requirements-dev.txt
            req_dev_path = os.path.join(temp_dir, "requirements-dev.txt")
            with open(req_dev_path, "w") as f:
                f.write("pytest==7.0.0\n")

            result = detect_uv_manifest(temp_dir)
            self.assertEqual(result, req_dev_path)


class TestGetUvVersion(TestCase):
    def test_get_uv_version_success(self):
        osutils_mock = Mock()
        osutils_mock.run_subprocess.return_value = (0, "uv 0.6.16", "")

        result = get_uv_version("uv", osutils_mock)
        self.assertEqual(result, "0.6.16")

    def test_get_uv_version_failure(self):
        osutils_mock = Mock()
        osutils_mock.run_subprocess.return_value = (1, "", "command not found")

        result = get_uv_version("uv", osutils_mock)
        self.assertIsNone(result)


class TestUvConfig(TestCase):
    def test_uv_config_defaults(self):
        config = UvConfig()
        args = config.to_uv_args()
        self.assertEqual(args, [])

    def test_uv_config_with_index_url(self):
        config = UvConfig(index_url="https://pypi.org/simple/")
        args = config.to_uv_args()
        self.assertIn("--index-url", args)
        self.assertIn("https://pypi.org/simple/", args)

    def test_uv_config_with_extra_index_urls(self):
        config = UvConfig(extra_index_urls=["https://extra1.com", "https://extra2.com"])
        args = config.to_uv_args()
        self.assertIn("--extra-index-url", args)
        self.assertIn("https://extra1.com", args)
        self.assertIn("https://extra2.com", args)

    def test_uv_config_with_cache_dir(self):
        config = UvConfig(cache_dir="/tmp/uv-cache")
        args = config.to_uv_args()
        self.assertIn("--cache-dir", args)
        self.assertIn("/tmp/uv-cache", args)

    def test_uv_config_no_cache(self):
        config = UvConfig(no_cache=True)
        args = config.to_uv_args()
        self.assertIn("--no-cache", args)

    def test_uv_config_prerelease(self):
        config = UvConfig(prerelease="allow")
        args = config.to_uv_args()
        self.assertIn("--prerelease", args)
        self.assertIn("allow", args)

    def test_uv_config_resolution(self):
        config = UvConfig(resolution="lowest")
        args = config.to_uv_args()
        self.assertIn("--resolution", args)
        self.assertIn("lowest", args)

    def test_uv_config_exclude_newer(self):
        config = UvConfig(exclude_newer="2023-01-01")
        args = config.to_uv_args()
        self.assertIn("--exclude-newer", args)
        self.assertIn("2023-01-01", args)

    def test_uv_config_generate_hashes(self):
        config = UvConfig(generate_hashes=True)
        args = config.to_uv_args()
        self.assertIn("--generate-hashes", args)
