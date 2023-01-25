import os
import tempfile
import shutil
import platform
from tarfile import ExtractError

from unittest import TestCase

from aws_lambda_builders.utils import copytree, get_goarch, extract_tarfile, glob_copy, get_option_from_args


class TestCopyTree(TestCase):
    def setUp(self):
        self.source = tempfile.mkdtemp()
        self.dest = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.source)
        shutil.rmtree(self.dest)

    def test_must_copy_files_recursively(self):
        file(self.source, "a", "file.txt")
        file(self.source, "a", "b", "file.txt")
        file(self.source, "a", "c", "file.txt")

        copytree(self.source, self.dest)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "file.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "b", "file.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "c", "file.txt")))

    def test_must_respect_excludes_list(self):
        file(self.source, ".git", "file.txt")
        file(self.source, "nested", ".aws-sam", "file.txt")
        file(self.source, "main.pyc")
        file(self.source, "a", "c", "file.txt")

        excludes = [".git", ".aws-sam", "*.pyc"]

        copytree(self.source, self.dest, ignore=shutil.ignore_patterns(*excludes))
        self.assertEqual(set(os.listdir(self.dest)), {"nested", "a"})
        self.assertEqual(set(os.listdir(os.path.join(self.dest, "nested"))), set())
        self.assertEqual(set(os.listdir(os.path.join(self.dest, "a"))), {"c"})
        self.assertEqual(set(os.listdir(os.path.join(self.dest, "a"))), {"c"})

    def test_must_respect_include_function(self):
        file(self.source, "nested", "folder", "file.txt")
        file(self.source, "main.pyc")
        file(self.source, "file.txt")

        def _include_check(file_name):
            return file_name.endswith(".txt")

        copytree(self.source, self.dest, include=_include_check)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "nested", "folder", "file.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "main.pyc")))

    def test_must_skip_if_source_folder_does_not_exist(self):
        copytree(os.path.join(self.source, "some-random-file"), self.dest)
        self.assertEqual(set(os.listdir(self.dest)), set())

    def test_must_return_valid_go_architecture(self):
        self.assertEqual(get_goarch("arm64"), "arm64")
        self.assertEqual(get_goarch("x86_64"), "amd64")
        self.assertEqual(get_goarch(""), "amd64")


class TestExtractTarFile(TestCase):
    def test_extract_tarfile_unpacks_a_tar(self):
        test_tar = os.path.join(os.path.dirname(__file__), "testdata", "test.tgz")
        test_dir = tempfile.mkdtemp()
        extract_tarfile(test_tar, test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_raise_exception_for_unsafe_tarfile(self):
        tar_filename = "path_reversal_win.tgz" if platform.system().lower() == "windows" else "path_reversal_uxix.tgz"
        test_tar = os.path.join(os.path.dirname(__file__), "testdata", tar_filename)
        test_dir = tempfile.mkdtemp()
        self.assertRaisesRegex(
            ExtractError, "Attempted Path Traversal in Tar File", extract_tarfile, test_tar, test_dir
        )


class TestGlobCopy(TestCase):
    def setUp(self):
        self.save_dir = os.getcwd()
        self.source = tempfile.mkdtemp()
        self.dest = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.source)
        shutil.rmtree(self.dest)
        os.chdir(self.save_dir)

    def test_copy_single_file(self):
        os.chdir(self.source)
        file(".", "a", "file.txt")
        glob_copy(os.path.join(".", "a", "file.txt"), self.dest)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "file.txt")))

    def test_copy_single_wildcard(self):
        os.chdir(self.source)
        file(".", "a", "b", "file1.txt")
        file(".", "a", "b", "file2.txt")
        glob_copy(os.path.join(".", "a", "b", "file*.txt"), self.dest)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "b", "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "b", "file2.txt")))

    def test_copy_list_with_wildcards(self):
        os.chdir(self.source)
        file(".", "a", "file1.txt")
        file(".", "a", "file2.txt")
        file(".", "b", "file3.txt")
        file(".", "c", "file4.txt")
        file(".", "c", "file5.txt")
        glob_copy([
            os.path.join(".", "a", "file*.txt"),
            os.path.join(".", "b", "file3.txt"),
            os.path.join(".", "c", "*")
            ], self.dest)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "a", "file2.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "b", "file3.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "c", "file4.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "c", "file5.txt")))

    def test_raise_exception_for_single_absolute_glob(self):
        test = "\\foo" if os.name == "nt" else "/foo"
        self.assertRaisesRegex(
            ValueError, "\"{test}\" is not a relative path".format(test=test), glob_copy, test, "./dest"
        )

    def test_raise_exception_for_list_item_absolute_glob(self):
        test = "\\bar" if os.name == "nt" else "/bar"
        self.assertRaisesRegex(
            ValueError, "\"{test}\" is not a relative path".format(test=test), glob_copy, [test], "./dest"
        )

    def test_raise_exception_for_not_found(self):
        test = "./not-going-to-exist-in-100-years"
        self.assertRaisesRegex(
            ValueError, "\"{test}\" not found".format(test=test), glob_copy, test, "./dest"
        )


def file(*args):
    path = os.path.join(*args)
    basedir = os.path.dirname(path)
    if not os.path.exists(basedir):
        os.makedirs(basedir)

    # empty file
    open(path, "a").close()


class TestGetOptionFromArgs(TestCase):

    def test_returns_none_on_no_args(self):
        self.assertEqual(None, get_option_from_args(None, "foo"))

    def test_returns_none_on_no_options_in_args(self):
        self.assertEqual(None, get_option_from_args({}, "foo"))

    def test_returns_none_on_none_options_in_args(self):
        self.assertEqual(None, get_option_from_args({"options": None}, "foo"))

    def test_returns_none_on_no_matching_option_in_args(self):
        self.assertEqual(None, get_option_from_args({"options": {}}, "foo"))

    def test_returns_value_on_matching_option_in_args(self):
        self.assertEqual("bar", get_option_from_args({"options": {"foo": "bar"}}, "foo"))
