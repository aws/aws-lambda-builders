import os
import tempfile
import shutil

from unittest import TestCase

from aws_lambda_builders.utils import copytree, get_goarch, extract_tarfile


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


def file(*args):
    path = os.path.join(*args)
    basedir = os.path.dirname(path)
    if not os.path.exists(basedir):
        os.makedirs(basedir)

    # empty file
    open(path, "a").close()
