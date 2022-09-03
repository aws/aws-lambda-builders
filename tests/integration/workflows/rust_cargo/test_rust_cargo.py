import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.workflows.rust_cargo.feature_flag import EXPERIMENTAL_FLAG_CARGO_LAMBDA


def rm_target_lambda(base):
    shutil.rmtree(os.path.join(base, "target", "lambda"), ignore_errors=True)


class TestRustCargo(TestCase):
    """
    Verifies that rust workflow works by building a Lambda using cargo
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.runtime = "provided"
        # this inherently tests that rust was was wired up though
        # the registry, a runtime error would be raised here if not
        self.builder = LambdaBuilder(language="rust", dependency_manager="cargo", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_failed_build_project(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "fail")

        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "Cargo.toml"),
                runtime=self.runtime,
                options={"artifact_executable_name": "fail"},
                experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
            )
            self.maxDiff = None
        self.assertTrue(
            raised.exception.args[0].startswith("RustCargoLambdaBuilder:CargoLambdaBuild - Builder Failed"),
            raised.exception.args[0],
        )

    def test_builds_hello_project(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "hello")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_hello_project_with_artifact_name(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "hello")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "hello"},
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_hello_project_for_arm64(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "hello")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            architecture="arm64",
            runtime=self.runtime,
            options={"artifact_executable_name": "hello"},
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_workspaces_project_with_bin_name(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "workspaces")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "foo"},
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_workspaces_project_with_package_option(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "workspaces")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            options={"cargo_lambda_flags": ["--package", "foo"]},
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_multi_function_project_with_function_a(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "multi-binary")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "function_a"},
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_multi_function_project_with_function_b(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "multi-binary")
        rm_target_lambda(source_dir)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Cargo.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "function_b"},
            experimental_flags=[EXPERIMENTAL_FLAG_CARGO_LAMBDA],
        )

        expected_files = {"bootstrap"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)
