import os
import shutil
import tempfile

from zipfile import ZipFile
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError


class TestJavaGradle(TestCase):
    SINGLE_BUILD_TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "testdata", "single-build")
    MULTI_BUILD_TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "testdata", "multi-build")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="java", dependency_manager="gradle", application_framework=None)
        self.runtime = "java11"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_build_single_build_with_deps(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = os.path.join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [p("aws", "lambdabuilders", "Main.class"), p("lib", "annotations-2.1.0.jar")]

        self.assert_artifact_contains_files(expected_files)

    def test_build_single_build_with_resources(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-resources")
        manifest_path = os.path.join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [
            p("aws", "lambdabuilders", "Main.class"),
            p("some_data.txt"),
            p("lib", "annotations-2.1.0.jar"),
        ]

        self.assert_artifact_contains_files(expected_files)

    def test_build_single_build_with_test_deps_test_jars_not_included(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-test-deps")
        manifest_path = os.path.join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [p("aws", "lambdabuilders", "Main.class"), p("lib", "annotations-2.1.0.jar")]

        self.assert_artifact_contains_files(expected_files)
        self.assert_artifact_not_contains_file(p("lib", "s3-2.1.0.jar"))

    def test_build_single_build_with_deps_gradlew(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps-gradlew")
        manifest_path = os.path.join(source_dir, "build.gradle")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            executable_search_paths=[source_dir],
        )
        expected_files = [p("aws", "lambdabuilders", "Main.class"), p("lib", "annotations-2.1.0.jar")]

        self.assert_artifact_contains_files(expected_files)

    def test_build_multi_build_with_deps_lambda1(self):
        parent_dir = os.path.join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = os.path.join(parent_dir, "lambda1", "build.gradle")

        lambda1_source = os.path.join(parent_dir, "lambda1")
        self.builder.build(lambda1_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda1_expected_files = [p("aws", "lambdabuilders", "Lambda1_Main.class"), p("lib", "annotations-2.1.0.jar")]
        self.assert_artifact_contains_files(lambda1_expected_files)

    def test_build_multi_build_with_deps_lambda2(self):
        parent_dir = os.path.join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = os.path.join(parent_dir, "lambda2", "build.gradle")

        lambda2_source = os.path.join(parent_dir, "lambda2")
        self.builder.build(lambda2_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda2_expected_files = [p("aws", "lambdabuilders", "Lambda2_Main.class"), p("lib", "annotations-2.1.0.jar")]
        self.assert_artifact_contains_files(lambda2_expected_files)

    def test_build_multi_build_with_deps_inter_module(self):
        parent_dir = os.path.join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps-inter-module")
        manifest_path = os.path.join(parent_dir, "lambda1", "build.gradle")

        lambda1_source = os.path.join(parent_dir, "lambda1")
        self.builder.build(lambda1_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda1_expected_files = [
            p("aws", "lambdabuilders", "Lambda1_Main.class"),
            p("lib", "annotations-2.1.0.jar"),
            p("lib", "common.jar"),
        ]
        self.assert_artifact_contains_files(lambda1_expected_files)

    def test_build_single_build_with_deps_broken(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps-broken")
        manifest_path = os.path.join(source_dir, "build.gradle")
        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        self.assertTrue(raised.exception.args[0].startswith("JavaGradleWorkflow:GradleBuild - Gradle Failed"))

    def assert_artifact_contains_files(self, files):
        for f in files:
            self.assert_artifact_contains_file(f)

    def assert_artifact_contains_file(self, p):
        self.assertTrue(os.path.exists(os.path.join(self.artifacts_dir, p)))

    def assert_artifact_not_contains_file(self, p):
        self.assertFalse(os.path.exists(os.path.join(self.artifacts_dir, p)))

    def assert_zip_contains(self, zip_path, files):
        with ZipFile(zip_path) as z:
            zip_names = set(z.namelist())
            self.assertTrue(set(files).issubset(zip_names))


def p(path, *comps):
    return os.path.join(path, *comps)
