import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestGoDep(TestCase):
    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

        os.environ["GOPATH"] = self.TEST_DATA_FOLDER

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "src", "nodeps")

        self.builder = LambdaBuilder(language="go", dependency_manager="dep", application_framework=None)

        self.runtime = "go1.x"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_builds_project_with_no_deps(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "src", "nodeps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Gopkg.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "main"},
        )

        expected_files = {"main"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_project_and_excludes_hidden_aws_sam(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "src", "excluded-files")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Gopkg.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "main"},
        )

        expected_files = {"main"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_project_with_no_gopkg_file(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "src", "no-gopkg")

        with self.assertRaises(WorkflowFailedError) as ex:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "Gopkg.toml"),
                runtime=self.runtime,
                options={"artifact_executable_name": "main"},
            )

        self.assertEqual(
            "GoDepBuilder:DepEnsure - Exec Failed: could not find project Gopkg.toml,"
            + " use dep init to initiate a manifest",
            str(ex.exception),
        )

    def test_builds_project_with_remote_deps(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "src", "remote-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "Gopkg.toml"),
            runtime=self.runtime,
            options={"artifact_executable_name": "main"},
        )

        expected_files = {"main"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    def test_builds_project_with_failed_remote_deps(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "src", "failed-remote")

        with self.assertRaises(WorkflowFailedError) as ex:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "Gopkg.toml"),
                runtime=self.runtime,
                options={"artifact_executable_name": "main"},
            )

        # The full message is super long, so part of it is fine.
        self.assertNotEqual(str(ex.exception).find("unable to deduce repository and source type for"), -1)
