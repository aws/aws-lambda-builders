import os
import pathlib
import shutil
import sys
import platform
import subprocess
import tempfile
import zipfile
from unittest import TestCase, skipIf
from unittest.mock import patch

from parameterized import parameterized, parameterized_class

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.utils import which
from aws_lambda_builders.workflows.python_uv.utils import EXPERIMENTAL_FLAG_BUILD_PERFORMANCE

IS_WINDOWS = platform.system().lower() == "windows"


@parameterized_class(("experimental_flags",), [([]), ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE])])
class TestPythonUvWorkflow(TestCase):
    """
    Verifies that `python_uv` workflow works by building a Lambda with simple dependencies
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")
    experimental_flags = []

    def setUp(self):
        self.source_dir = self.TEST_DATA_FOLDER
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()

        self.manifest_path_requirements = os.path.join(self.TEST_DATA_FOLDER, "requirements-simple.txt")
        self.manifest_path_pyproject = os.path.join(self.TEST_DATA_FOLDER, "pyproject.toml")

        # PIP-equivalent test files for compatibility validation
        self.manifest_path_numpy = os.path.join(self.TEST_DATA_FOLDER, "requirements-numpy.txt")
        self.manifest_path_wrapt = os.path.join(self.TEST_DATA_FOLDER, "requirements-wrapt.txt")
        self.manifest_path_invalid = os.path.join(self.TEST_DATA_FOLDER, "requirements-invalid.txt")

        self.test_data_files = {
            "__init__.py",
            "main.py",
            "requirements-simple.txt",
            "pyproject.toml",
            "requirements-numpy.txt",
            "requirements-wrapt.txt",
            "requirements-invalid.txt",
            "pyproject-numpy.toml",
            "pyproject-wrapt.toml",
        }

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_uses_requirements_txt_file(self):
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_requirements,
            runtime="python3.9",
            experimental_flags=self.experimental_flags,
        )

        expected_files = self.test_data_files.union({"six.py", "six-1.16.0.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files.intersection(output_files), expected_files)

    @parameterized.expand(
        [
            ("python3.11", "x86_64", "x86_64", 17, 28),
            ("python3.11", "arm64", "aarch64", 17, 28),
            ("python3.12", "x86_64", "x86_64", 34, 35),
            ("python3.12", "arm64", "aarch64", 34, 35),
        ]
    )
    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_selects_lambda_compatible_wheel(self, runtime, architecture, wheel_arch, supported, too_new):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source_dir = root / "function"
            source_dir.mkdir()
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            for glibc_minor in (supported, too_new):
                tag = f"py3-none-manylinux_2_{glibc_minor}_{wheel_arch}"
                with zipfile.ZipFile(wheelhouse / f"platform_demo-1.0.0-{tag}.whl", "w") as wheel:
                    wheel.writestr("platform_demo.py", f"GLIBC_MINOR = {glibc_minor}\n")
                    wheel.writestr(
                        "platform_demo-1.0.0.dist-info/METADATA",
                        "Metadata-Version: 2.1\nName: platform-demo\nVersion: 1.0.0\n",
                    )
                    wheel.writestr(
                        "platform_demo-1.0.0.dist-info/WHEEL",
                        f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: {tag}\n",
                    )
                    wheel.writestr("platform_demo-1.0.0.dist-info/RECORD", "")
            manifest_path = source_dir / "requirements.txt"
            manifest_path.write_text("platform-demo==1.0.0\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"UV_NO_INDEX": "1", "UV_OFFLINE": "1", "UV_FIND_LINKS": wheelhouse.as_uri()},
            ):
                LambdaBuilder(language="python", dependency_manager="uv", application_framework=None).build(
                    str(source_dir),
                    self.artifacts_dir,
                    self.scratch_dir,
                    str(manifest_path),
                    runtime=runtime,
                    architecture=architecture,
                    experimental_flags=self.experimental_flags,
                )

            self.assertEqual(
                (pathlib.Path(self.artifacts_dir) / "platform_demo.py").read_text(encoding="utf-8"),
                f"GLIBC_MINOR = {supported}\n",
            )

    @parameterized.expand([(False,), (True,)])
    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_installs_local_wheel_from_requirements_directory(self, relative_paths):
        # Keep paths on the checkout's drive so relative paths also work on Windows.
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
            root = pathlib.Path(directory)
            source_dir = root / "function"
            source_dir.mkdir()
            wheel_path = source_dir / "local_demo-1.0.0-py3-none-any.whl"
            module = "VALUE = 'from function directory'\n"
            with zipfile.ZipFile(wheel_path, "w") as wheel:
                wheel.writestr("local_demo.py", module)
                wheel.writestr(
                    "local_demo-1.0.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: local-demo\nVersion: 1.0.0\n",
                )
                wheel.writestr(
                    "local_demo-1.0.0.dist-info/WHEEL",
                    "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
                )
                wheel.writestr("local_demo-1.0.0.dist-info/RECORD", "")
            manifest_path = source_dir / "requirements.txt"
            manifest_path.write_text(f"./{wheel_path.name}\n", encoding="utf-8")
            artifacts_dir = root / "artifacts"
            scratch_dir = root / "scratch"
            paths = [source_dir, artifacts_dir, scratch_dir, manifest_path]
            paths = [os.path.relpath(path) if relative_paths else str(path) for path in paths]
            original_cwd = os.getcwd()

            LambdaBuilder(language="python", dependency_manager="uv", application_framework=None).build(
                *paths,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

            self.assertEqual((artifacts_dir / "local_demo.py").read_text(encoding="utf-8"), module)
            self.assertFalse((source_dir / "artifacts").exists())
            self.assertEqual(os.getcwd(), original_cwd)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_uses_pyproject_toml_file(self):
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_pyproject,
            runtime="python3.9",
            experimental_flags=self.experimental_flags,
        )

        expected_files = self.test_data_files.union({"six.py", "six-1.16.0.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files.intersection(output_files), expected_files)

    @parameterized.expand(
        [
            (cutoff, package_cutoff, changed)
            for cutoff, package_cutoff in (
                ("2024-01-01", None),
                ("30 days", None),
                ("2024-01-01", "2023-01-01"),
                ("2024-01-01", "30 days"),
            )
            for changed in (False, True)
        ]
    )
    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_preserves_existing_lock_options(self, cutoff, package_cutoff, changed_manifest):
        with tempfile.TemporaryDirectory() as source_dir:
            manifest_path = pathlib.Path(source_dir) / "pyproject.toml"
            manifest_path.write_text(
                '[project]\nname = "locked-demo"\nversion = "1.0.0"\nrequires-python = ">=3.13"\ndependencies = []\n'
                f'\n[tool.uv]\nexclude-newer = "{cutoff}"\n',
                encoding="utf-8",
            )
            subprocess.run(
                [
                    shutil.which("uv"),
                    "lock",
                    "--offline",
                    "--python",
                    "3.13",
                    "--resolution",
                    "lowest-direct",
                    "--prerelease",
                    "allow",
                    "--fork-strategy",
                    "fewest",
                ]
                + (["--exclude-newer-package", f"six={package_cutoff}"] if package_cutoff else []),
                cwd=source_dir,
                check=True,
                capture_output=True,
            )
            lock_path = pathlib.Path(source_dir) / "uv.lock"
            lock_contents = lock_path.read_bytes()
            self.assertIn(b"exclude-newer", lock_contents)
            if cutoff == "30 days":
                self.assertIn(b'exclude-newer-span = "P30D"', lock_contents)
            if package_cutoff:
                self.assertIn(b"[options.exclude-newer-package]", lock_contents)
            if changed_manifest:
                dependency_dir = pathlib.Path(source_dir) / "dep"
                dependency_dir.mkdir()
                (dependency_dir / "pyproject.toml").write_text(
                    '[project]\nname = "local-dep"\nversion = "1.0.0"\n', encoding="utf-8"
                )
                manifest_path.write_text(
                    manifest_path.read_text(encoding="utf-8").replace(
                        "dependencies = []", 'dependencies = ["local-dep"]'
                    )
                    + '\n[tool.uv.sources]\nlocal-dep = {path = "dep"}\n',
                    encoding="utf-8",
                )

            def build():
                LambdaBuilder(language="python", dependency_manager="uv", application_framework=None).build(
                    source_dir,
                    self.artifacts_dir,
                    self.scratch_dir,
                    str(manifest_path),
                    runtime="python3.13",
                    experimental_flags=self.experimental_flags,
                )

            with patch.dict(os.environ, {"UV_OFFLINE": "1"}):
                if changed_manifest:
                    with self.assertRaisesRegex(WorkflowFailedError, "--locked"):
                        build()
                else:
                    build()

            self.assertEqual(lock_path.read_bytes(), lock_contents)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_with_dependencies_dir(self):
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_requirements,
            runtime="python3.9",
            dependencies_dir=self.dependencies_dir,
            experimental_flags=self.experimental_flags,
        )

        expected_files = self.test_data_files
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files.intersection(output_files), expected_files)

        expected_dependencies = {"six.py", "six-1.16.0.dist-info"}
        dependencies_files = set(os.listdir(self.dependencies_dir))
        self.assertEqual(expected_dependencies.intersection(dependencies_files), expected_dependencies)

        # combine_dependencies defaults to True, so dependencies must also be copied into the artifacts dir.
        self.assertEqual(expected_dependencies.intersection(output_files), expected_dependencies)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_numpy_successfully(self):
        """Test that UV can build numpy (same as PIP workflow test)"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_numpy,
            runtime="python3.13",
            experimental_flags=self.experimental_flags,
        )

        # Check that numpy was built successfully
        output_files = set(os.listdir(self.artifacts_dir))
        expected_numpy_files = {"numpy", "numpy-2.1.2.dist-info", "numpy.libs"}

        # Verify numpy files are present
        for expected_file in expected_numpy_files:
            self.assertIn(expected_file, output_files, f"Expected {expected_file} in build output")

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_fails_with_wrapt_python313(self):
        """Test that UV fails with wrapt on Python 3.13 (same as PIP workflow)"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        # Should fail due to Python 3.13 incompatibility
        with self.assertRaises(WorkflowFailedError):
            builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_wrapt,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_fails_with_invalid_requirements(self):
        """Test that UV properly handles invalid requirements syntax (same as PIP workflow)"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        # Should fail due to invalid syntax (boto3=1.19.99 instead of boto3==1.19.99)
        with self.assertRaises(WorkflowFailedError) as ctx:
            builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_invalid,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

        # Verify error message mentions the syntax issue
        error_message = str(ctx.exception)
        self.assertIn("no such comparison operator", error_message)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_uses_pyproject_with_lock_file(self):
        """Test that UV uses existing uv.lock file for reproducible builds"""
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_pyproject,
            runtime="python3.9",
            experimental_flags=self.experimental_flags,
        )

        # uv.lock exists in testdata alongside pyproject.toml
        # Verify dependencies were installed from lock file
        expected_files = {"six.py", "six-1.16.0.dist-info"}
        output_files = set(os.listdir(self.artifacts_dir))
        for expected_file in expected_files:
            self.assertIn(expected_file, output_files)

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_with_arm64_architecture(self):
        """Test that UV builds for ARM64 architecture"""
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_numpy,
            runtime="python3.12",
            architecture="arm64",
            experimental_flags=self.experimental_flags,
        )

        # Verify numpy was built for ARM64 by checking WHEEL metadata
        wheel_path = os.path.join(self.artifacts_dir, "numpy-2.1.2.dist-info", "WHEEL")
        self.assertTrue(os.path.exists(wheel_path), "WHEEL metadata file should exist")

        with open(wheel_path) as f:
            wheel_content = f.read()
        self.assertIn("aarch64", wheel_content, "WHEEL should contain aarch64 platform tag")

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_with_x86_64_architecture(self):
        """Test that UV builds for x86_64 architecture (default)"""
        builder = LambdaBuilder(
            language="python",
            dependency_manager="uv",
            application_framework=None,
        )
        builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_numpy,
            runtime="python3.12",
            architecture="x86_64",
            experimental_flags=self.experimental_flags,
        )

        # Verify numpy was built for x86_64 by checking WHEEL metadata
        wheel_path = os.path.join(self.artifacts_dir, "numpy-2.1.2.dist-info", "WHEEL")
        self.assertTrue(os.path.exists(wheel_path), "WHEEL metadata file should exist")

        with open(wheel_path) as f:
            wheel_content = f.read()
        self.assertIn("x86_64", wheel_content, "WHEEL should contain x86_64 platform tag")

    @skipIf(which("uv") is None, "uv not available")
    def test_workflow_builds_numpy_with_pyproject(self):
        """Test that UV can build numpy using pyproject.toml format"""
        builder = LambdaBuilder(language="python", dependency_manager="uv", application_framework=None)

        # Create a temporary directory with pyproject.toml (UV only recognizes exact name)
        temp_source_dir = tempfile.mkdtemp()
        try:
            # Copy main.py to temp directory
            shutil.copy(os.path.join(self.TEST_DATA_FOLDER, "main.py"), temp_source_dir)
            shutil.copy(os.path.join(self.TEST_DATA_FOLDER, "__init__.py"), temp_source_dir)

            # Copy pyproject-numpy.toml as pyproject.toml
            shutil.copy(
                os.path.join(self.TEST_DATA_FOLDER, "pyproject-numpy.toml"),
                os.path.join(temp_source_dir, "pyproject.toml"),
            )

            pyproject_path = os.path.join(temp_source_dir, "pyproject.toml")

            builder.build(
                temp_source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                pyproject_path,
                runtime="python3.13",
                experimental_flags=self.experimental_flags,
            )

            # Check that numpy was built successfully
            output_files = set(os.listdir(self.artifacts_dir))
            expected_numpy_files = {"numpy", "numpy-2.1.2.dist-info", "numpy.libs"}

            # Verify numpy files are present
            for expected_file in expected_numpy_files:
                self.assertIn(expected_file, output_files, f"Expected {expected_file} in build output")

        finally:
            shutil.rmtree(temp_source_dir)
