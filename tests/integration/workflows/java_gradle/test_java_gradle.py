import os
import shutil
import tempfile
import platform

from unittest import TestCase
from pathlib import Path
from os.path import join

from parameterized import parameterized_class


from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from tests.integration.workflows.common_test_utils import (
    does_folder_contain_all_files,
    does_folder_contain_file,
    folder_should_not_contain_files,
)


@parameterized_class(
    ("runtime",),
    [
        ["java8"],
        ["java11"],
        ["java17"],
        ["java21"],
    ],
)
class TestJavaGradle(TestCase):
    # Have to use str(Path(__file__).resolve()) here to workaround a Windows VSCode issue
    # __file__ will return lower case drive letters. Ex: c:\folder\test.py instead of C:\folder\test.py
    # This will break the hashing algorithm we use for build directory generation
    SINGLE_BUILD_TEST_DATA_DIR = join(os.path.dirname(str(Path(__file__).resolve())), "testdata", "single-build")
    MULTI_BUILD_TEST_DATA_DIR = join(os.path.dirname(str(Path(__file__).resolve())), "testdata", "multi-build")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()

        scratch_folder_override = None
        if platform.system().lower() == "windows" and os.getenv("GITHUB_ACTIONS"):
            # lucashuy: there is some really odd behaviour where
            # gradle will refuse to work it is run within
            # the default TEMP folder location in Github Actions
            #
            # use the runner's home directory as a workaround
            scratch_folder_override = os.getenv("userprofile")

        self.scratch_dir = tempfile.mkdtemp(dir=scratch_folder_override)

        self.dependencies_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="java", dependency_manager="gradle", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    def test_build_single_build_with_deps(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        expected_files = [join("aws", "lambdabuilders", "Main.class"), join("lib", "annotations-2.1.0.jar")]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))

    def test_build_single_build_with_resources(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-resources")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
            join("some_data.txt"),
            join("lib", "annotations-2.1.0.jar"),
        ]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))

    def test_build_single_build_with_test_deps_test_jars_not_included(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-test-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [join("aws", "lambdabuilders", "Main.class"), join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, join("lib", "s3-2.1.0.jar")))

    def test_build_single_build_with_deps_gradlew(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
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
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(parent_dir, "lambda1", "build.gradle")

        lambda1_source = join(parent_dir, "lambda1")

        self.builder.build(lambda1_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda1_expected_files = [
            join("aws", "lambdabuilders", "Lambda1_Main.class"),
            join("lib", "annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, lambda1_expected_files))

    def test_build_multi_build_with_deps_lambda2(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(parent_dir, "lambda2", "build.gradle")

        lambda2_source = join(parent_dir, "lambda2")
        self.builder.build(lambda2_source, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)

        lambda2_expected_files = [
            join("aws", "lambdabuilders", "Lambda2_Main.class"),
            join("lib", "annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, lambda2_expected_files))

    def test_build_multi_build_with_deps_inter_module(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, self.runtime, "with-deps-inter-module")
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
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps-broken")
        manifest_path = join(source_dir, "build.gradle")
        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        self.assertTrue(raised.exception.args[0].startswith("JavaGradleWorkflow:GradleBuild - Gradle Failed"))

    def test_build_single_build_with_deps_dir(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(source_dir, "build.gradle")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
        )
        artifact_expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
            join("lib", "annotations-2.1.0.jar"),
        ]
        dependencies_expected_files = [join("lib", "annotations-2.1.0.jar")]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))

    def test_build_multi_build_with_deps_dir_inter_module(self):
        parent_dir = join(self.MULTI_BUILD_TEST_DATA_DIR, self.runtime, "with-deps-inter-module")
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
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
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

    def test_build_with_layers_and_scope(self):
        # first build layer and validate
        self.validate_layer_build()
        # then build function which uses this layer as dependency with provided scope
        self.validate_function_build()

    def validate_layer_build(self):
        layer_source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "layer")
        layer_manifest_path = join(layer_source_dir, "build.gradle")
        self.builder.build(
            layer_source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            layer_manifest_path,
            runtime=self.runtime,
            is_building_layer=True,
        )
        artifact_expected_files = [
            join("lib", "aws-lambda-java-core-1.2.0.jar"),
            join("lib", "common-layer-gradle-1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))

    def validate_function_build(self):
        self.setUp()  # re-initialize folders
        function_source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-layer-deps")
        function_manifest_path = join(function_source_dir, "build.gradle")
        self.builder.build(
            function_source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            function_manifest_path,
            runtime=self.runtime,
            is_building_layer=False,
        )
        artifact_expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
        ]
        artifact_not_expected_files = [
            join("lib", "com.amazonaws.aws-lambda-java-core-1.2.0.jar"),
            join("lib", "common-layer-1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))
        self.assertTrue(folder_should_not_contain_files(self.artifacts_dir, artifact_not_expected_files))
