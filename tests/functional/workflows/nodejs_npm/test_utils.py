import os
import shutil
import sys
import tempfile

from unittest import TestCase

from aws_lambda_builders.workflows.nodejs_npm import utils


class TestOSUtils(TestCase):
    def setUp(self):
        self.osutils = utils.OSUtils()

    def test_copy_file_copies_existing_file_into_a_dir(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()

        self.osutils.copy_file(test_file, test_dir)

        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test.tgz"}, output_files)

    def test_copy_file_copies_existing_file_into_a_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()

        self.osutils.copy_file(test_file, os.path.join(test_dir, "copied_test.tgz"))

        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"copied_test.tgz"}, output_files)

    def test_remove_file_removes_existing_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        copied_file = os.path.join(test_dir, "copied_test.tgz")
        shutil.copy(test_file, copied_file)

        self.osutils.remove_file(copied_file)

        self.assertFalse(os.path.isfile(copied_file))

    def test_file_exists_checking_if_file_exists_in_a_dir(self):
        existing_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        nonexisting_file = os.path.join(os.path.dirname(__file__), "test_data", "nonexisting.tgz")

        self.assertTrue(self.osutils.file_exists(existing_file))
        self.assertFalse(self.osutils.file_exists(nonexisting_file))

    def test_extract_tarfile_unpacks_a_tar(self):
        test_tar = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()

        self.osutils.extract_tarfile(test_tar, test_dir)

        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_dirname_returns_directory_for_path(self):
        dirname = self.osutils.dirname(sys.executable)

        self.assertEqual(dirname, os.path.dirname(sys.executable))

    def test_abspath_returns_absolute_path(self):
        result = self.osutils.abspath(".")

        self.assertTrue(os.path.isabs(result))
        self.assertEqual(result, os.path.abspath("."))

    def test_joinpath_joins_path_components(self):
        result = self.osutils.joinpath("a", "b", "c")

        self.assertEqual(result, os.path.join("a", "b", "c"))

    def test_popen_runs_a_process_and_returns_outcome(self):
        cwd_py = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "cwd.py")

        p = self.osutils.popen([sys.executable, cwd_py], stdout=self.osutils.pipe, stderr=self.osutils.pipe)

        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.getcwd())

    def test_popen_can_accept_cwd(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata")

        p = self.osutils.popen(
            [sys.executable, "cwd.py"], stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=testdata_dir
        )

        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.path.abspath(testdata_dir))

    def test_dir_exists(self):
        self.assertFalse(self.osutils.dir_exists("20201210_some_directory_that_should_not_exist"))

        temp_dir = tempfile.mkdtemp()

        self.assertTrue(self.osutils.dir_exists(temp_dir))

        shutil.rmtree(temp_dir)

    def test_mkdir_makes_directory(self):
        dir_to_create = os.path.join(tempfile.gettempdir(), "20201210_some_directory_that_should_not_exist")
        self.assertFalse(os.path.isdir(dir_to_create))

        self.osutils.mkdir(dir_to_create)

        self.assertTrue(os.path.isdir(dir_to_create))

        shutil.rmtree(dir_to_create)

    def test_mkdirs_makes_directory_and_subdir(self):
        dir_to_create = os.path.join(tempfile.gettempdir(), "20201210_some_directory_that_should_not_exist")
        subdir_to_create = os.path.join(dir_to_create, "subdirectory_that_should_not_exist")
        self.assertFalse(os.path.isdir(dir_to_create))
        self.assertFalse(os.path.isdir(subdir_to_create))

        self.osutils.makedirs(subdir_to_create)

        self.assertTrue(os.path.isdir(dir_to_create))
        self.assertTrue(os.path.isdir(subdir_to_create))
        shutil.rmtree(dir_to_create)

    def test_normpath_normalizes_paths(self):
        self.assertEqual("/my/path/with/package.json", self.osutils.normpath("/my/path/with/without/../package.json"))

    def test_open_file_opens_file_for_reading(self):
        temp_dir = tempfile.mkdtemp()

        file_to_open = os.path.join(temp_dir, "test_open.txt")

        with open(file_to_open, "w") as fid:
            fid.write("this is text")

        with self.osutils.open_file(file_to_open) as fid:
            content = fid.read()

        self.assertEqual("this is text", content)

        shutil.rmtree(temp_dir)

    def test_open_file_opens_file_for_writing(self):
        temp_dir = tempfile.mkdtemp()

        file_to_open = os.path.join(temp_dir, "test_open.txt")

        with self.osutils.open_file(file_to_open, "w") as fid:
            fid.write("this is some other text")

        with self.osutils.open_file(file_to_open) as fid:
            content = fid.read()

        self.assertEqual("this is some other text", content)

        shutil.rmtree(temp_dir)

    def test_walk_walks_tree(self):
        all_files = []

        for (_, _, files) in self.osutils.walk(os.path.dirname(__file__)):
            for f in files:
                all_files.append(f)

        # Only testing those two as OSes enjoy adding other hidden files (like .DS_Store)
        self.assertTrue("test_utils.py" in all_files)
        self.assertTrue("test.tgz" in all_files)


class TestDependencyUtils(TestCase):
    def test_is_local_dependency_file_prefix(self):
        self.assertTrue(utils.DependencyUtils.is_local_dependency("file:./local/dep"))

    def test_is_local_dependency_dot_prefix(self):
        self.assertTrue(utils.DependencyUtils.is_local_dependency("./local/dep"))

    def test_is_local_dependency_package_name(self):
        self.assertFalse(utils.DependencyUtils.is_local_dependency("typescript"))

    def test_is_local_dependency_invalid(self):
        self.assertFalse(utils.DependencyUtils.is_local_dependency(None))
