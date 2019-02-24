import os
import shutil
import tempfile


from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder


class TestDotnetDep(TestCase):
    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        self.builder = LambdaBuilder(language="dotnet",
                                     dependency_manager="cli-package",
                                     application_framework=None)

        self.runtime = "dotnetcore2.1"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_with_defaults_file(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "WithDefaultsFile")

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                           source_dir,
                           runtime=self.runtime)

        expected_files = {"Amazon.Lambda.Core.dll",
                          "Amazon.Lambda.Serialization.Json.dll",
                          "Newtonsoft.Json.dll",
                          "WithDefaultsFile.deps.json",
                          "WithDefaultsFile.dll",
                          "WithDefaultsFile.pdb",
                          "WithDefaultsFile.runtimeconfig.json"}

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEquals(expected_files, output_files)

    def test_require_parameters(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "RequireParameters")

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                           source_dir,
                           runtime=self.runtime,
                           options={"--framework": "netcoreapp2.1", "--configuration": "Debug"})

        expected_files = {"Amazon.Lambda.Core.dll",
                          "Amazon.Lambda.Serialization.Json.dll",
                          "Newtonsoft.Json.dll",
                          "RequireParameters.deps.json",
                          "RequireParameters.dll",
                          "RequireParameters.pdb",
                          "RequireParameters.runtimeconfig.json"}

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEquals(expected_files, output_files)
