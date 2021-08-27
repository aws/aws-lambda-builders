import os
import shutil
import tempfile

from pathlib import Path
from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from tests.integration.workflows.common_test_utils import does_folder_contain_all_files, does_folder_contain_file

p = os.path.join


class TestJavaMaven(TestCase):
    SINGLE_BUILD_TEST_DATA_DIR = os.path.join(os.path.dirname(Path(__file__).resolve()), "testdata", "single-build")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()
        self.builder = LambdaBuilder(language="java", dependency_manager="maven", application_framework=None)
        self.runtime = "java8"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    def test_build_single_build_with_deps_resources_exclude_test_jars(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = os.path.join(source_dir, "pom.xml")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [
            p("aws", "lambdabuilders", "Main.class"),
            p("some_data.txt"),
            p("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, p("lib", "junit-4.12.jar")))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_single_build_no_deps(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "no-deps")
        manifest_path = os.path.join(source_dir, "pom.xml")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        expected_files = [p("aws", "lambdabuilders", "Main.class"), p("some_data.txt")]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, p("lib")))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_single_build_with_deps_broken(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps-broken")
        manifest_path = os.path.join(source_dir, "pom.xml")
        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        self.assertTrue(raised.exception.args[0].startswith("JavaMavenWorkflow:MavenBuild - Maven Failed"))
        self.assert_src_dir_not_touched(source_dir)

    def test_build_single_build_with_deps_resources_exclude_test_jars_deps_dir(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, "with-deps")
        manifest_path = os.path.join(source_dir, "pom.xml")
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest_path,
            runtime=self.runtime,
            dependencies_dir=self.dependencies_dir,
        )
        expected_files = [
            p("aws", "lambdabuilders", "Main.class"),
            p("some_data.txt"),
            p("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]

        dependencies_expected_files = [
            p("lib", "software.amazon.awssdk.annotations-2.1.0.jar"),
        ]
        self.assertTrue(does_folder_contain_all_files(self.artifacts_dir, expected_files))
        self.assertTrue(does_folder_contain_all_files(self.dependencies_dir, dependencies_expected_files))
        self.assertFalse(does_folder_contain_file(self.artifacts_dir, p("lib", "junit-4.12.jar")))
        self.assert_src_dir_not_touched(source_dir)

    def assert_src_dir_not_touched(self, source_dir):
        self.assertFalse(os.path.exists(os.path.join(source_dir, "target")))
