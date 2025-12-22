import os
import shutil
import tempfile
import json
from parameterized import parameterized

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.supported_runtimes import DOTNET_RUNTIMES


def get_dotnet_test_params():
    """Generate test parameters from DOTNET_RUNTIMES for standard Lambda functions."""
    params = []
    for runtime in DOTNET_RUNTIMES:
        version_num = runtime.replace("dotnet", "")
        version = f"{version_num}.0"
        test_project = f"WithDefaultsFile{version_num}"
        params.append((runtime, version, test_project))
    return params


def get_custom_runtime_test_params():
    """Generate test parameters from DOTNET_RUNTIMES for custom runtime builds.

    Note: dotnet6 is excluded as it doesn't support custom runtime in the same way.
    """
    params = []
    for runtime in DOTNET_RUNTIMES:
        if runtime == "dotnet6":
            continue
        version_num = runtime.replace("dotnet", "")
        version = f"{version_num}.0"
        test_project = f"CustomRuntime{version_num}"
        params.append((runtime, version, test_project))
    return params


class TestDotnetBase(TestCase):
    """
    Base class for dotnet tests
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="dotnet", dependency_manager="cli-package", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def verify_architecture(self, deps_file_name, expected_architecture, version):
        deps_file = pathlib.Path(self.artifacts_dir, deps_file_name)

        if not deps_file.exists():
            self.fail("Failed verifying architecture, {} file not found".format(deps_file_name))

        with open(str(deps_file)) as f:
            deps_json = json.loads(f.read())
        target_name = ".NETCoreApp,Version=v{}/{}".format(version, expected_architecture)
        target = deps_json.get("runtimeTarget").get("name")

        self.assertEqual(target, target_name)

    def verify_execute_permissions(self, entrypoint_file_name):
        entrypoint_file_path = os.path.join(self.artifacts_dir, entrypoint_file_name)
        self.assertTrue(os.access(entrypoint_file_path, os.X_OK))


class TestDotnet(TestDotnetBase):
    """
    Tests for dotnet
    """

    def setUp(self):
        super(TestDotnet, self).setUp()

    @parameterized.expand(get_dotnet_test_params())
    def test_with_defaults_file(self, runtime, version, test_project):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, test_project)

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime)

        expected_files = {
            "Amazon.Lambda.Core.dll",
            "Amazon.Lambda.Serialization.Json.dll",
            "Newtonsoft.Json.dll",
            "WithDefaultsFile.deps.json",
            "WithDefaultsFile.dll",
            "WithDefaultsFile.pdb",
            "WithDefaultsFile.runtimeconfig.json",
        }

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)
        self.verify_architecture("WithDefaultsFile.deps.json", "linux-x64", version)

    @parameterized.expand(get_dotnet_test_params())
    def test_with_defaults_file_x86(self, runtime, version, test_project):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, test_project)

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime, architecture=X86_64)

        expected_files = {
            "Amazon.Lambda.Core.dll",
            "Amazon.Lambda.Serialization.Json.dll",
            "Newtonsoft.Json.dll",
            "WithDefaultsFile.deps.json",
            "WithDefaultsFile.dll",
            "WithDefaultsFile.pdb",
            "WithDefaultsFile.runtimeconfig.json",
        }

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)
        self.verify_architecture("WithDefaultsFile.deps.json", "linux-x64", version)

    @parameterized.expand(get_dotnet_test_params())
    def test_with_defaults_file_arm64(self, runtime, version, test_project):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, test_project)

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime, architecture=ARM64)

        expected_files = {
            "Amazon.Lambda.Core.dll",
            "Amazon.Lambda.Serialization.Json.dll",
            "Newtonsoft.Json.dll",
            "WithDefaultsFile.deps.json",
            "WithDefaultsFile.dll",
            "WithDefaultsFile.pdb",
            "WithDefaultsFile.runtimeconfig.json",
        }

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)
        self.verify_architecture("WithDefaultsFile.deps.json", "linux-arm64", version)

    @parameterized.expand(get_custom_runtime_test_params())
    def test_with_custom_runtime(self, runtime, version, test_project):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, test_project)

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime, architecture=X86_64)

        expected_files = {
            "Amazon.Lambda.Core.dll",
            "Amazon.Lambda.RuntimeSupport.dll",
            "Amazon.Lambda.Serialization.SystemTextJson.dll",
            "bootstrap",
            "bootstrap.deps.json",
            "bootstrap.dll",
            "bootstrap.pdb",
            "bootstrap.runtimeconfig.json",
        }

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)
        self.verify_architecture("bootstrap.deps.json", "linux-x64", version)
        # Execute permissions are required for custom runtimes which bootstrap themselves, otherwise `sam local invoke`
        # won't have permission to run the file
        self.verify_execute_permissions("bootstrap")
