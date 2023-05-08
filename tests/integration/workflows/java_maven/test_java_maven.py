import os
import shutil
import tempfile

from pathlib import Path
from unittest import TestCase
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
    ],
)
class TestJavaMaven(TestCase):
    # Have to use str(Path(__file__).resolve()) here to workaround a Windows VSCode issue
    # __file__ will return lower case drive letters. Ex: c:\folder\test.py instead of C:\folder\test.py
    # This will break the hashing algorithm we use for build directory generation
    SINGLE_BUILD_TEST_DATA_DIR = join(os.path.dirname(str(Path(__file__).resolve())), "testdata", "single-build")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="java", dependency_manager="maven", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    def test_build_single_build_with_deps_resources_exclude_test_jars(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(source_dir, "pom.xml")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
            join("some_data.txt"),
            join("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, join("lib", "junit-4.12.jar")))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_single_build_no_deps(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "no-deps")
        manifest_path = join(source_dir, "pom.xml")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [join("aws", "lambdabuilders", "Main.class"), join("some_data.txt")]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, join("lib")))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_single_build_with_deps_broken(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps-broken")
        manifest_path = join(source_dir, "pom.xml")
        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        self.assertTrue(raised.exception.args[0].startswith("JavaMavenWorkflow:MavenBuild - Maven Failed"))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_single_build_with_deps_resources_exclude_test_jars_deps_dir(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(source_dir, "pom.xml")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
        )
        expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
            join("some_data.txt"),
            join("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]

        dependencies_expected_files = [
            join("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, join("lib", "junit-4.12.jar")))
        self.assert_src_dir_not_touched(source_dir)

    def assert_src_dir_not_touched(self, source_dir):
        self.assertFalse(os.path.exists(join(source_dir, "target")))

    def test_build_single_build_with_deps_resources_exclude_test_jars_deps_dir_without_combine_dependencies(self):
        source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-deps")
        manifest_path = join(source_dir, "pom.xml")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )
        artifact_expected_files = [
            join("aws", "lambdabuilders", "Main.class"),
            join("some_data.txt"),
        ]

        dependencies_expected_files = [
            join("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]

        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, join("lib", "junit-4.12.jar")))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_with_layers_and_scope(self):
        # first build layer and validate
        self.validate_layer_build()
        # then build function which uses this layer as dependency with provided scope
        self.validate_function_build()

    def validate_layer_build(self):
        layer_source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "layer")
        layer_manifest_path = join(layer_source_dir, "pom.xml")
        self.builder.build(
            layer_source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            layer_manifest_path,
            runtime=self.runtime,
            is_building_layer=True,
        )
        artifact_expected_files = [
            join("lib", "com.amazonaws.aws-lambda-java-core-1.2.0.jar"),
            join("lib", "common-layer-1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, artifact_expected_files))
        self.assert_src_dir_not_touched(layer_source_dir)

    def validate_function_build(self):
        self.setUp()  # re-initialize folders
        function_source_dir = join(self.SINGLE_BUILD_TEST_DATA_DIR, self.runtime, "with-layer-deps")
        function_manifest_path = join(function_source_dir, "pom.xml")
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
        self.assert_src_dir_not_touched(function_source_dir)
