import os
import sys
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

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

    @parameterized.expand(
        [
            # (files in the function directory, expected manifest)
            ("metadata-only pyproject", {"pyproject.toml": "[project]\nname = 'test'\n"}, "requirements.txt"),
            ("tool-only pyproject", {"pyproject.toml": "[tool.ruff]\nline-length = 120\n"}, "requirements.txt"),
            (
                "pyproject declares dependencies",
                {"pyproject.toml": "[project]\nname = 'test'\ndependencies = ['six']\n"},
                "pyproject.toml",
            ),
            (
                "pyproject declares empty dependencies",
                {"pyproject.toml": "[project]\nname = 'test'\ndependencies = []\n"},
                "requirements.txt",
            ),
            (
                "pyproject has dynamic dependencies",
                {"pyproject.toml": "[project]\nname = 'test'\ndynamic = ['dependencies']\n"},
                "requirements.txt",
            ),
            (
                "pyproject has non-list dynamic",
                {"pyproject.toml": "[project]\nname = 'test'\ndynamic = 'dependencies'\n"},
                "requirements.txt",
            ),
            (
                "empty dependencies with uv.lock",
                {"pyproject.toml": "[project]\nname = 'test'\ndependencies = []\n", "uv.lock": "version = 1\n"},
                "pyproject.toml",
            ),
            (
                "uv.lock beside pyproject",
                {"pyproject.toml": "[project]\nname = 'test'\n", "uv.lock": "version = 1\n"},
                "pyproject.toml",
            ),
            ("unparseable pyproject", {"pyproject.toml": "[project\n"}, "requirements.txt"),
        ]
    )
    def test_detect_uv_manifest_pyproject_and_requirements(self, _name, files, expected):
        with tempfile.TemporaryDirectory() as temp_dir:
            files = {"requirements.txt": "requests==2.28.0\n", **files}
            for name, content in files.items():
                with open(os.path.join(temp_dir, name), "w") as f:
                    f.write(content)

            self.assertEqual(detect_uv_manifest(temp_dir), os.path.join(temp_dir, expected))

    def test_detect_uv_manifest_without_toml_parser_keeps_requirements(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "pyproject.toml"), "w") as f:
                f.write("[project]\nname = 'test'\ndependencies = ['six']\n")
            req_path = os.path.join(temp_dir, "requirements.txt")
            with open(req_path, "w") as f:
                f.write("requests==2.28.0\n")

            # Python 3.10 without tomli: the declared dependencies cannot be read
            with patch.dict(sys.modules, {"tomllib": None, "tomli": None}):
                self.assertEqual(detect_uv_manifest(temp_dir), req_path)

    @parameterized.expand([("requirements-dev.txt",), ("requirements-test.txt",)])
    def test_detect_uv_manifest_ignores_dev_and_test_requirements(self, requirements_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, requirements_file), "w") as f:
                f.write("pytest==7.0.0\n")

            self.assertIsNone(detect_uv_manifest(temp_dir))

    def test_detect_uv_manifest_pyproject_over_dev_requirements(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject_path = os.path.join(temp_dir, "pyproject.toml")
            with open(pyproject_path, "w") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(temp_dir, "requirements-dev.txt"), "w") as f:
                f.write("pytest==7.0.0\n")

            self.assertEqual(detect_uv_manifest(temp_dir), pyproject_path)

    def test_detect_uv_manifest_prod_requirements(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            req_prod_path = os.path.join(temp_dir, "requirements-prod.txt")
            with open(req_prod_path, "w") as f:
                f.write("requests==2.28.0\n")
            with open(os.path.join(temp_dir, "requirements-dev.txt"), "w") as f:
                f.write("pytest==7.0.0\n")

            self.assertEqual(detect_uv_manifest(temp_dir), req_prod_path)


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
