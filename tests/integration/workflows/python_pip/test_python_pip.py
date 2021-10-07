import os
import shutil
import sys
import platform
import tempfile
from unittest import TestCase, skipIf
import mock

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
import logging

logger = logging.getLogger("aws_lambda_builders.workflows.python_pip.workflow")
IS_WINDOWS = platform.system().lower() == "windows"


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

        self.test_data_files = {
            "__init__.py",
            "main.py",
            "requirements-invalid.txt",
            "requirements-numpy.txt",
            "local-dependencies",
        }

        self.builder = LambdaBuilder(language="python", dependency_manager="pip", application_framework=None)
        self.runtime = "{language}{major}.{minor}".format(
            language=self.builder.capability.language, major=sys.version_info.major, minor=sys.version_info.minor
        )
        self.runtime_mismatch = {
            "python3.6": "python2.7",
            "python3.7": "python2.7",
            "python2.7": "python3.8",
            "python3.8": "python2.7",
            "python3.9": "python2.7",
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

    # Temporarily skipping this test in Windows
    # Fails and we are not sure why: pip version/multiple Python versions in path/os/pypa issue?
    # TODO: Revisit when we deprecate Python2
    @skipIf(IS_WINDOWS, "Skip in windows tests")
    def test_must_build_python_project(self):
        self.builder.build(
            self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid, runtime=self.runtime
        )

        if self.runtime == "python2.7":
            expected_files = self.test_data_files.union({"numpy", "numpy-1.15.4.data", "numpy-1.15.4.dist-info"})
        elif self.runtime == "python3.6":
            self.check_architecture_in("numpy-1.17.4.dist-info", ["manylinux2010_x86_64", "manylinux1_x86_64"])
            expected_files = self.test_data_files.union({"numpy", "numpy-1.17.4.dist-info"})
        else:
            self.check_architecture_in("numpy-1.20.3.dist-info", ["manylinux2010_x86_64", "manylinux1_x86_64"])
            expected_files = self.test_data_files.union({"numpy", "numpy-1.20.3.dist-info", "numpy.libs"})

        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    def test_must_build_python_project_with_arm_architecture(self):
        if self.runtime != "python3.8":
            self.skipTest("{} is not supported on ARM architecture".format(self.runtime))
        ### Check the wheels
        self.builder.build(
            self.source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            self.manifest_path_valid,
            runtime=self.runtime,
            architecture="arm64",
        )
        expected_files = self.test_data_files.union({"numpy", "numpy.libs", "numpy-1.20.3.dist-info"})
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        self.check_architecture_in("numpy-1.20.3.dist-info", ["manylinux2014_aarch64"])

    # Temporarily skipping this test in Windows
    # Fails and we are not sure why: pip version/multiple Python versions in path/os/pypa issue?
    # TODO: Revisit when we deprecate Python2
    @skipIf(IS_WINDOWS, "Skip in windows tests")
    def test_mismatch_runtime_python_project(self):
        # NOTE : Build still works if other versions of python are accessible on the path. eg: /usr/bin/python2.7
        # is still accessible within a python 3 virtualenv.
        try:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path_valid,
                runtime=self.runtime_mismatch[self.runtime],
            )
        except WorkflowFailedError as ex:
            self.assertIn("Binary validation failed", str(ex))

    def test_runtime_validate_python_project_fail_open_unsupported_runtime(self):
        with self.assertRaises(WorkflowFailedError):
            self.builder.build(
                self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_valid, runtime="python2.8"
            )

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    def test_must_resolve_local_dependency(self):
        source_dir = os.path.join(self.source_dir, "local-dependencies")
        manifest = os.path.join(source_dir, "requirements.txt")
        path_to_package = os.path.join(self.source_dir, "local-dependencies")
        # pip resolves dependencies in requirements files relative to the current working directory
        # need to make sure the correct path is used in the requirements file locally and in CI
        with open(manifest, "w") as f:
            f.write(str(path_to_package))
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir, manifest, runtime=self.runtime)
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

    def test_must_fail_to_resolve_dependencies(self):

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                self.source_dir, self.artifacts_dir, self.scratch_dir, self.manifest_path_invalid, runtime=self.runtime
            )

        # In Python2 a 'u' is now added to the exception string. To account for this, we see if either one is in the
        # output
        message_in_exception = "Invalid requirement: 'adfasf=1.2.3'" in str(
            ctx.exception
        ) or "Invalid requirement: u'adfasf=1.2.3'" in str(ctx.exception)
        self.assertTrue(message_in_exception)

    def test_must_log_warning_if_requirements_not_found(self):
        with mock.patch.object(logger, "warning") as mock_warning:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join("non", "existent", "manifest"),
                runtime=self.runtime,
            )
        expected_files = self.test_data_files
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
        mock_warning.assert_called_once_with(
            "requirements.txt file not found. Continuing the build without dependencies."
        )

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    def test_without_download_dependencies_with_dependencies_dir(self):
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
            runtime=self.runtime,
            download_dependencies=False,
            dependencies_dir=self.dependencies_dir,
        )

        # if download_dependencies is False and dependencies is empty, the artifacts_dir should just copy files from
        # source package
        expected_files = set(os.listdir(path_to_package))
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(output_files, expected_files)

    @skipIf(IS_WINDOWS, "Skip in windows tests")
    def test_with_download_dependencies_and_dependencies_dir(self):
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
            runtime=self.runtime,
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
    def test_without_download_dependencies_without_dependencies_dir(self):
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
                runtime=self.runtime,
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
    def test_without_combine_dependencies(self):
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
            runtime=self.runtime,
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
