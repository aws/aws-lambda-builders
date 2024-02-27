import os
import shutil
import tempfile

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from unittest import TestCase
from parameterized import parameterized


from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError

from tests.integration.workflows.go_modules.utils import get_executable_arch
from tests.integration.workflows.go_modules.utils import get_md5_hexdigest


class TestGoWorkflow(TestCase):
    """
    Verifies that `go` workflow works by building a Lambda using Go Modules
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="go", dependency_manager="modules", application_framework=None)
        self.runtime = "go1.x"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_builds_project_without_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main"},
        )
        expected_files = {"no-deps-main"}
        output_files = set(os.listdir(self.artifacts_dir))
        print(output_files)
        self.assertEqual(expected_files, output_files)

    def test_builds_project_with_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "with-deps-main"},
        )
        expected_files = {"with-deps-main"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_fails_if_modules_cannot_resolve_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-deps")
        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "go.mod"),
                runtime=self.runtime,
                options={"artifact_executable_name": "failed"},
            )
        self.assertIn("GoModulesBuilder:Build - Builder Failed: ", str(ctx.exception))

    def test_build_defaults_to_x86_architecture(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        built_x86_architecture = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main-amd64"},
        )
        pathname = Path(self.artifacts_dir, "no-deps-main-amd64")
        self.assertEqual(get_executable_arch(pathname), "x64")

    def test_builds_x86_architecture(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        built_x86_architecture = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main-amd64"},
            architecture="x86_64",
        )
        pathname = Path(self.artifacts_dir, "no-deps-main-amd64")
        self.assertEqual(get_executable_arch(pathname), "x64")

    def test_builds_arm64_architecture(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        built_arm_architecture = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main-arm64"},
            architecture="arm64",
        )
        pathname = Path(self.artifacts_dir, "no-deps-main-arm64")
        self.assertEqual(get_executable_arch(pathname), "AArch64")

    def test_builds_with_trimpath(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        built_trimpath = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main-trimpath", "trim_go_path": True},
            architecture="x86_64",
        )
        pathname = Path(self.artifacts_dir, "no-deps-main-trimpath")
        self.assertEqual(get_executable_arch(pathname), "x64")

    def test_builds_without_trimpath_are_not_equal(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        built_no_trimpath = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main", "trim_go_path": False},
            architecture="x86_64",
        )

        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-copy")
        built_no_trimpath_copy = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main-copy", "trim_go_path": False},
            architecture="x86_64",
        )
        pathname = Path(self.artifacts_dir, "no-deps-main")
        pathnameOfCopy = Path(self.artifacts_dir, "no-deps-main-copy")
        self.assertNotEqual(get_md5_hexdigest(pathname), get_md5_hexdigest(pathnameOfCopy))

    def test_builds_with_trimpath_are_equal(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        built_with_trimpath = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main", "trim_go_path": True},
            architecture="x86_64",
        )

        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps-copy")
        built_with_trimpath_copy = self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "no-deps-main-copy", "trim_go_path": True},
            architecture="x86_64",
        )
        pathname = Path(self.artifacts_dir, "no-deps-main")
        pathnameOfCopy = Path(self.artifacts_dir, "no-deps-main-copy")
        self.assertEqual(get_md5_hexdigest(pathname), get_md5_hexdigest(pathnameOfCopy))

    def test_builds_project_with_nested_dir(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "nested_build_folder")
        package_dir = os.path.join(source_dir, "cmd/helloWorld")
        self.builder.build(
            package_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=self.runtime,
            options={"artifact_executable_name": "helloWorld"},
        )
        expected_files = {"helloWorld"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("provided", "bootstrap"), ("go1.x", "helloWorld")])
    def test_binary_named_bootstrap_for_provided_runtime(self, runtime, expected_binary):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "go.mod"),
            runtime=runtime,
            options={"artifact_executable_name": "helloWorld"},
        )
        expected_files = {expected_binary}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
