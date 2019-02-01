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
        self.builder = LambdaBuilder(language='java', dependency_manager='gradle', application_framework=None)
        self.runtime = 'java'

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_build_single_build_with_deps(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, 'with-deps')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        zip_name = 'with-deps.zip'
        expected_contents = ['aws/lambdabuilders/Main.class', 'lib/annotations-2.1.0.jar']

        self.assertTrue(zip_name in os.listdir(self.artifacts_dir))
        self.assert_zip_contains(os.path.join(self.artifacts_dir, zip_name), expected_contents)

    def test_build_single_build_with_resources(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, 'with-resources')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        zip_name = 'with-resources.zip'
        expected_contents = ['aws/lambdabuilders/Main.class', 'some_data.txt', 'lib/annotations-2.1.0.jar']

        self.assertTrue(zip_name in os.listdir(self.artifacts_dir))
        self.assert_zip_contains(os.path.join(self.artifacts_dir, zip_name), expected_contents)

    def test_build_single_build_with_test_deps_test_jars_not_included(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, 'with-test-deps')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        zip_name = 'with-test-deps.zip'
        expected_contents = ['aws/lambdabuilders/Main.class', 'lib/annotations-2.1.0.jar']

        self.assertTrue(zip_name in os.listdir(self.artifacts_dir))
        zip_path = os.path.join(self.artifacts_dir, zip_name)
        self.assert_zip_contains(zip_path, expected_contents)
        self.assert_zip_not_contains(zip_path, ['lib/s3-2.1.0.jar'])

    def test_build_single_build_with_deps_gradlew(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, 'with-deps-gradlew')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        zip_name = 'with-deps-gradlew.zip'
        expected_contents = ['aws/lambdabuilders/Main.class', 'lib/annotations-2.1.0.jar']

        self.assertTrue(zip_name in os.listdir(self.artifacts_dir))
        self.assert_zip_contains(os.path.join(self.artifacts_dir, zip_name), expected_contents)

    def test_build_multi_build_with_deps(self):
        source_dir = os.path.join(self.MULTI_BUILD_TEST_DATA_DIR, 'with-deps')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        artifact_mapping = {'lambda1': 'l1', 'lambda2': 'l2'}

        for _, d in artifact_mapping.items():
            os.mkdir(os.path.join(self.artifacts_dir, d))

        options = {'artifact_mapping': artifact_mapping}

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, options=options,
                           runtime=self.runtime)

        lambda1_zip_name = 'lambda1.zip'
        lambda2_zip_name = 'lambda2.zip'

        lambda1_artifact_dir = os.path.join(self.artifacts_dir, artifact_mapping['lambda1'])
        lambda2_artifact_dir = os.path.join(self.artifacts_dir, artifact_mapping['lambda2'])

        self.assertTrue(lambda1_zip_name in os.listdir(lambda1_artifact_dir))
        self.assertTrue(lambda2_zip_name in os.listdir(lambda2_artifact_dir))

        lambda1_zip_path = os.path.join(lambda1_artifact_dir, lambda1_zip_name)
        lambda2_zip_path = os.path.join(lambda2_artifact_dir, lambda2_zip_name)

        lambda1_expected_contents = ['aws/lambdabuilders/Lambda1_Main.class', 'lib/annotations-2.1.0.jar']
        self.assert_zip_contains(lambda1_zip_path, lambda1_expected_contents)

        lambda2_expected_contents = ['aws/lambdabuilders/Lambda2_Main.class', 'lib/annotations-2.1.0.jar']
        self.assert_zip_contains(lambda2_zip_path, lambda2_expected_contents)

    def test_build_multi_build_with_deps_inter_module(self):
        source_dir = os.path.join(self.MULTI_BUILD_TEST_DATA_DIR, 'with-deps-inter-module')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        artifact_mapping = {'lambda1': 'l1', 'lambda2': 'l2'}

        for _, d in artifact_mapping.items():
            os.mkdir(os.path.join(self.artifacts_dir, d))

        options = {'artifact_mapping': artifact_mapping}

        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, options=options,
                           runtime=self.runtime)

        lambda1_zip_name = 'lambda1.zip'
        lambda2_zip_name = 'lambda2.zip'

        lambda1_artifact_dir = os.path.join(self.artifacts_dir, artifact_mapping['lambda1'])
        lambda2_artifact_dir = os.path.join(self.artifacts_dir, artifact_mapping['lambda2'])

        self.assertTrue(lambda1_zip_name in os.listdir(lambda1_artifact_dir))
        self.assertTrue(lambda2_zip_name in os.listdir(lambda2_artifact_dir))

        lambda1_zip_path = os.path.join(lambda1_artifact_dir, lambda1_zip_name)
        lambda2_zip_path = os.path.join(lambda2_artifact_dir, lambda2_zip_name)

        lambda1_expected_contents = ['aws/lambdabuilders/Lambda1_Main.class', 'lib/annotations-2.1.0.jar',
                                     'lib/common.jar']
        self.assert_zip_contains(lambda1_zip_path, lambda1_expected_contents)

        lambda2_expected_contents = ['aws/lambdabuilders/Lambda2_Main.class', 'lib/annotations-2.1.0.jar']
        self.assert_zip_contains(lambda2_zip_path, lambda2_expected_contents)

    def test_build_single_build_with_deps_broken(self):
        source_dir = os.path.join(self.SINGLE_BUILD_TEST_DATA_DIR, 'with-deps-broken')
        manifest_path = os.path.join(source_dir, 'build.gradle')
        with self.assertRaises(WorkflowFailedError) as raised:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest_path, runtime=self.runtime)
        self.assertTrue(raised.exception.args[0].startswith('JavaGradleWorkflow:GradleBuild - Gradle Failed'))

    def assert_zip_contains(self, zip_path, files):
        with ZipFile(zip_path) as z:
            zip_names = set(z.namelist())
            self.assertTrue(set(files).issubset(zip_names))

    def assert_zip_not_contains(self, zip_path, files):
        with ZipFile(zip_path) as z:
            zip_names = set(z.namelist())
            self.assertTrue(not set(files).issubset(zip_names))
