import os
import shutil
import tempfile

from unittest import TestCase
from pathlib import Path
from os.path import join


from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from tests.integration.workflows.common_test_utils import does_folder_contain_all_files, does_folder_contain_file


class TestJavaGradle(TestCase):
    # Have to use str(Path(__file__).resolve()) here to workaround a Windows VSCode issue
    # __file__ will return lower case drive letters. Ex: c:\folder\test.py instead of C:\folder\test.py
    # This will break the hashing algorithm we use for build directory generation
    SINGLE_BUILD_TEST_DATA_DIR = join(os.path.dirname(str(Path(__file__).resolve())), "testdata", "single-build")
    MULTI_BUILD_TEST_DATA_DIR = join(os.path.dirname(str(Path(__file__).resolve())), "testdata", "multi-build")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="java", dependency_manager="gradle", application_framework=None)
        self.runtime = "java11"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    def test_build_single_build_with_deps(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [join("aws", "lambdabuilders", "Main.class"), join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))

    def test_build_single_build_with_resources(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-resources")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
            join("some_data.txt"),
            join("lib", "annotations-2.1.0.jar"),
        ]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))

    def test_build_single_build_with_test_deps_test_jars_not_included(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-test-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [join("aws", "lambdabuilders", "Main.class"), join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, join("lib", "s3-2.1.0.jar")))

    def test_build_single_build_with_deps_gradlew(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps-gradlew")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            executable_search_paths=[source_dir],
        )
        expected_files = [join("aws", "lambdabuilders", "Main.class"), join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))

    def test_build_multi_build_with_deps_lambda1(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = join(parent_dir, "lambda1", "build.gradle")

        lambda1_source = join(parent_dir, "lambda1")
        self.builder.build(lambda1_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda1_expected_files = [
            join("aws", "lambdabuilders", "Lambda1_Main.class"),
            join("lib", "annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, lambda1_expected_files))

    def test_build_multi_build_with_deps_lambda2(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = join(parent_dir, "lambda2", "build.gradle")

        lambda2_source = join(parent_dir, "lambda2")
        self.builder.build(lambda2_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda2_expected_files = [
            join("aws", "lambdabuilders", "Lambda2_Main.class"),
            join("lib", "annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, lambda2_expected_files))

    def test_build_multi_build_with_deps_inter_module(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps-inter-module")
        manifest_path = join(parent_dir, "lambda1", "build.gradle")

        lambda1_source = join(parent_dir, "lambda1")
        self.builder.build(lambda1_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda1_expected_files = [
            join("aws", "lambdabuilders", "Lambda1_Main.class"),
            join("lib", "annotations-2.1.0.jar"),
            join("lib", "common.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, lambda1_expected_files))

    def test_build_single_build_with_deps_broken(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps-broken")
        manifest_path = join(source_dir, "build.gradle")
        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        self.assertTrue(raised.exception.args[0].startswith("JavaGradleWorkflow:GradleBuild - Gradle Failed"))

    def test_build_single_build_with_deps_dir(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
        )
        artifact_expected_files = [join("aws", "lambdabuilders", "Main.class"), join("lib", "annotations-2.1.0.jar")]
        dependencies_expected_files = [join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))

    def test_build_multi_build_with_deps_dir_inter_module(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, "with-deps-inter-module")
        manifest_path = join(parent_dir, "lambda1", "build.gradle")

        lambda1_source = join(parent_dir, "lambda1")
        self.builder.build(
            lambda1_source,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
        )

        lambda1_expected_files = [
            join("aws", "lambdabuilders", "Lambda1_Main.class"),
            join("lib", "annotations-2.1.0.jar"),
            join("lib", "common.jar"),
        ]
        dependencies_expected_files = [
            join("lib", "annotations-2.1.0.jar"),
            join("lib", "common.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, lambda1_expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))

    def test_build_single_build_with_deps_dir_wtihout_combine_dependencies(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )
        artifact_expected_files = [join("aws", "lambdabuilders", "Main.class")]
        dependencies_expected_files = [join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))
