import os
import shutil
import tempfile
from unittest import TestCase

from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils, DependencyUtils
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm


class TestDependencyUtils(TestCase):
    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.osutils = OSUtils()
        self.subprocess_npm = SubprocessNpm(self.osutils)
        self.uut = DependencyUtils()
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_ship_module(self):
        self.uut.ship_module(
            os.path.join(self.TEST_DATA_FOLDER, "module_1"),
            self.scratch_dir,
            self.artifacts_dir,
            self.osutils,
            self.subprocess_npm,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(os.path.join(self.artifacts_dir, "package")))
        self.assertEqual(output_files, expected_files)

    def test_get_local_dependencies_with_none(self):
        dependencies = self.uut.get_local_dependencies(
            os.path.join(self.TEST_DATA_FOLDER, "module_1", "package.json"),
            self.osutils,
        )

        self.assertEqual(dependencies, {})

    def test_get_local_dependencies_with_some(self):
        dependencies = self.uut.get_local_dependencies(
            os.path.join(self.TEST_DATA_FOLDER, "module_2", "package.json"),
            self.osutils,
        )

        self.assertEqual(dependencies, {"@mockcompany/module-a": "file:../modules/module_a"})

    def test_is_local_dependency_when_is(self):
        self.assertEqual(self.uut.is_local_dependency("file:../modules/module_a"), True)

    def test_is_local_dependency_when_is_not(self):
        self.assertEqual(self.uut.is_local_dependency("1.2.3"), False)

    def test_is_local_dependency_when_is_not_string(self):
        self.assertEqual(self.uut.is_local_dependency(None), False)

    def test_package_dependencies(self):
        package = self.uut.package_dependencies(
            os.path.join(self.TEST_DATA_FOLDER, "module_1", "package.json"),
            self.scratch_dir,
            {},
            self.osutils,
            self.subprocess_npm,
        )
        self.assertEqual(os.path.basename(package), "nodejs_npm_unit_tests_module_1-1.0.0.tgz")

    def test_update_manifest(self):
        scratch_manifest = os.path.join(self.scratch_dir, "scratch_package.json")
        self.osutils.copy_file(os.path.join(self.TEST_DATA_FOLDER, "module_2", "package.json"), scratch_manifest)
        self.uut.update_manifest(scratch_manifest, "@mockcompany/module-a", "interim/path.tgz", self.osutils)
