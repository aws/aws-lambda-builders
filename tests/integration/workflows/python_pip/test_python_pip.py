import os
import shutil
import platform
import tempfile
from unittest import TestCase, skipIf
import mock
from parameterized import parameterized

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
import logging

logger = logging.getLogger("aws_lambda_builders.workflows.python_pip.workflow")
IS_WINDOWS = platform.system().lower() == "windows"
NOT_ARM = platform.processor() != "aarch64"
ARM_RUNTIMES = {"python3.8", "python3.9"}
SUPPORTED_PYTHON_VERSIONS = set(["python3.6", "python3.7"] + list(ARM_RUNTIMES))


class TestPythonPipWorkflow(TestCase):
    """
    Verifies that `python_pip` workflow works by building a Lambda that requires Numpy
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.source_dir = self.TEST_DATA_FOLDER
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()

        self.manifest_path_valid = os.path.join(self.TEST_DATA_FOLDER, "requirements-numpy.txt")
        self.manifest_path_invalid = os.path.join(self.TEST_DATA_FOLDER, "requirements-invalid.txt")
        self.manifest_path_sdist = os.path.join(self.TEST_DATA_FOLDER, "requirements-wrapt.txt")

        self.test_data_files = {
            "__init__.py",
            "main.py",
            "requirements-invalid.txt",
            "requirements-numpy.txt",
            "requirements-wrapt.txt",
            "local-dependencies",
        }

        self.builder = LambdaBuilder(language="python", dependency_manager="pip", application_framework=None)
        self.runtime_mismatch = {
            "python3.6": "python3.7",
            "python3.7": "python3.8",
            "python3.8": "python3.9",
            "python3.9": "python3.7",
        }

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)

    def check_architecture_in(self, library, architectures):
        wheel_architectures = []
        with open(os.path.join(self.artifacts_dir, library, "WHEEL")) as wheel:
            for line in wheel:
                if line.startswith("Tag:"):
                    wheel_architecture = line.rstrip().split("-")[-1]
                    if wheel_architecture in architectures:
                        return  # Success
                    wheel_architectures.append(wheel_architecture)
        self.fail(
            "Wheel architectures [{}] not found in [{}]".format(
                ", ".join(wheel_architectures), ", ".join(architectures)
            )
        )

    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_must_build_python_project(self, runtime):
        self.builder.build(
            self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid, runtime=runtime
        )

        if runtime == "python3.6":
            self.check_architecture_in("numpy-1.17.4.dist-info", ["manylinux2010_x86_64", "manylinux1_x86_64"])
            expected_files = self.test_data_files.union({"numpy", "numpy-1.17.4.dist-info"})
        else:
            self.check_architecture_in("numpy-1.20.3.dist-info", ["manylinux2010_x86_64", "manylinux1_x86_64"])
            expected_files = self.test_data_files.union({"numpy", "numpy-1.20.3.dist-info", "numpy.libs"})

        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_must_build_python_project_from_sdist_with_arm(self, runtime):
        if NOT_ARM or runtime not in ARM_RUNTIMES:
            self.skipTest("{} is not supported on ARM architecture".format(runtime))

        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_sdist,
            runtime=runtime,
            architecture="arm64",
        )
        expected_files = self.test_data_files.union({"wrapt", "wrapt-1.13.3.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        self.check_architecture_in("wrapt-1.13.3.dist-info", ["linux_aarch64"])

    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_must_build_python_project_with_arm_architecture(self, runtime):
        if runtime not in ARM_RUNTIMES:
            self.skipTest("{} is not supported on ARM architecture".format(runtime))
        ### Check the wheels
        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_valid,
            runtime=runtime,
            architecture="arm64",
        )
        expected_files = self.test_data_files.union({"numpy", "numpy.libs", "numpy-1.20.3.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        self.check_architecture_in("numpy-1.20.3.dist-info", ["manylinux2014_aarch64"])

    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_mismatch_runtime_python_project(self, runtime):
        # NOTE : Build still works if other versions of python are accessible on the path. eg: /usr/bin/python3.7
        # is still accessible within a python 3.8 virtualenv.
        try:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_valid,
                runtime=self.runtime_mismatch[runtime],
            )
        except WorkflowFailedError as ex:
            self.assertIn("Binary validation failed", str(ex))

    def test_runtime_validate_python_project_fail_open_unsupported_runtime(self):
        with self.assertRaises(WorkflowFailedError):
            self.builder.build(
                self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid, runtime="python2.8"
            )

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_must_resolve_local_dependency(self, runtime):
        source_dir = os.path.join(self.source_dir, "local-dependencies")
        manifest = os.path.join(source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(manifest, "w") as f:
            f.write(str(path_to_package))
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest, runtime=runtime)
        expected_files = {
            "local_package",
            "local_package-0.0.0.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
            "setup.py",
            "requirements.txt",
        }
        output_files = set(os.listdir(self.artifacts_dir))
        for f in expected_files:
            self.assertIn(f, output_files)

    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_must_fail_to_resolve_dependencies(self, runtime):
        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_invalid, runtime=runtime
            )

        message_in_exception = "Invalid requirement: 'boto3=1.19.99'" in str(ctx.exception)
        self.assertTrue(message_in_exception)

    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_must_log_warning_if_requirements_not_found(self, runtime):
        with mock.patch.object(logger, "warning") as mock_warning:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join("non", "existent", "manifest"),
                runtime=runtime,
            )
        expected_files = self.test_data_files
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
        mock_warning.assert_called_once_with(
            "requirements.txt file not found. Continuing the build without dependencies."
        )

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_without_download_dependencies_with_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.source_dir, "local-dependencies")
        manifest = os.path.join(source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(manifest, "w") as f:
            f.write(str(path_to_package))
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest,
            runtime=runtime,
            download_dependencies=False,
            dependencies_dir=self.dependencies_dir,
        )

        # if download_dependencies is False and dependencies is empty, the artifacts_dir should just copy files from
        # source package
        expected_files = set(os.listdir(path_to_package))
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(output_files, expected_files)

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_with_download_dependencies_and_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.source_dir, "local-dependencies")
        manifest = os.path.join(source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(manifest, "w") as f:
            f.write(str(path_to_package))
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest,
            runtime=runtime,
            download_dependencies=True,
            dependencies_dir=self.dependencies_dir,
        )

        # build artifact should be same as usual
        expected_files = {
            "local_package",
            "local_package-0.0.0.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
            "setup.py",
            "requirements.txt",
        }
        output_files = set(os.listdir(self.artifacts_dir))
        for f in expected_files:
            self.assertIn(f, output_files)

        # if download_dependencies is True and dependencies dir is provided, we should have a copy of dependencies in the dependencies dir
        expected_dependencies_files = {
            "local_package",
            "local_package-0.0.0.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
        }
        dependencies_files = set(os.listdir(self.dependencies_dir))
        for f in expected_dependencies_files:
            self.assertIn(f, dependencies_files)

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_without_download_dependencies_without_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.source_dir, "local-dependencies")
        manifest = os.path.join(source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(manifest, "w") as f:
            f.write(str(path_to_package))
        with mock.patch.object(logger, "info") as mock_info:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                manifest,
                runtime=runtime,
                download_dependencies=False,
                dependencies_dir=None,
            )

        # if download_dependencies is False and dependencies is None, the artifacts_dir should just copy files from
        # source package
        expected_files = set(os.listdir(path_to_package))
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(output_files, expected_files)

        mock_info.assert_called_once_with(
            "download_dependencies is False and dependencies_dir is None. Copying the source files into the "
            "artifacts directory. "
        )

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    @parameterized.expand(SUPPORTED_PYTHON_VERSIONS)
    def test_without_combine_dependencies(self, runtime):
        source_dir = os.path.join(self.source_dir, "local-dependencies")
        manifest = os.path.join(source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(manifest, "w") as f:
            f.write(str(path_to_package))
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            manifest,
            runtime=runtime,
            download_dependencies=True,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )

        expected_files = os.listdir(source_dir)
        output_files = set(os.listdir(self.artifacts_dir))
        for f in expected_files:
            self.assertIn(f, output_files)

        # if download_dependencies is True and dependencies dir is provided, we should have a copy of dependencies in the dependencies dir
        expected_dependencies_files = {
            "local_package",
            "local_package-0.0.0.dist-info",
            "requests",
            "requests-2.23.0.dist-info",
        }
        dependencies_files = set(os.listdir(self.dependencies_dir))
        for f in expected_dependencies_files:
            self.assertIn(f, dependencies_files)
