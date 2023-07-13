import os
import shutil
import tempfile
import json

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.architecture import ARM64, X86_64


class TestDotnetBase(TestCase):
    """
    Base class for dotnet tests
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="dotnet", dependency_manager="cli-package", application_framework=None)
        self.runtime = "dotnet6"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def verify_architecture(self, deps_file_name, expected_architecture, version=None):
        deps_file = pathlib.Path(self.artifacts_dir, deps_file_name)

        if not deps_file.exists():
            self.fail("Failed verifying architecture, {} file not found".format(deps_file_name))

        with open(str(deps_file)) as f:
            deps_json = json.loads(f.read())
        version = version or self.runtime[-3:]
        target_name = ".NETCoreApp,Version=v{}/{}".format(version, expected_architecture)
        target = deps_json.get("runtimeTarget").get("name")

        self.assertEqual(target, target_name)

    def verify_execute_permissions(self, entrypoint_file_name):
        entrypoint_file_path = os.path.join(self.artifacts_dir, entrypoint_file_name)
        self.assertTrue(os.access(entrypoint_file_path, os.X_OK))


class TestDotnet6(TestDotnetBase):
    """
    Tests for dotnet 6
    """

    def setUp(self):
        super(TestDotnet6, self).setUp()
        self.runtime = "dotnet6"

    def test_with_defaults_file(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "WithDefaultsFile6")

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime=self.runtime)

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
        self.verify_architecture("WithDefaultsFile.deps.json", "linux-x64", version="6.0")

    def test_with_defaults_file_x86(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "WithDefaultsFile6")

        self.builder.build(
            source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime=self.runtime, architecture=X86_64
        )

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
        self.verify_architecture("WithDefaultsFile.deps.json", "linux-x64", version="6.0")

    def test_with_defaults_file_arm64(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "WithDefaultsFile6")

        self.builder.build(
            source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime=self.runtime, architecture=ARM64
        )

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
        self.verify_architecture("WithDefaultsFile.deps.json", "linux-arm64", version="6.0")

    def test_with_custom_runtime(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "CustomRuntime6")

        self.builder.build(
            source_dir, self.artifacts_dir, self.scratch_dir, source_dir, runtime=self.runtime, architecture=X86_64
        )

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
        self.verify_architecture("bootstrap.deps.json", "linux-x64", version="6.0")
        # Execute permissions are required for custom runtimes which bootstrap themselves, otherwise `sam local invoke`
        # won't have permission to run the file
        self.verify_execute_permissions("bootstrap")
