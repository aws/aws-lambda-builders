import os
import tempfile
import shutil
import platform
from tarfile import ExtractError

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

    def test_must_maintain_symlinks_if_enabled(self):
        # set up symlinked file and directory
        source_target_file_path = file(self.source, "targetfile.txt")
        source_symlink_file_path = os.path.join(self.source, "symlinkfile.txt")
        os.symlink(source_target_file_path, source_symlink_file_path)

        source_target_dir_path = os.path.join(self.source, "targetdir")
        os.makedirs(source_target_dir_path)
        source_symlink_dir_path = os.path.join(self.source, "symlinkdir")
        os.symlink(source_target_dir_path, source_symlink_dir_path)

        # call copytree
        copytree(self.source, self.dest, maintain_symlinks=True)

        # assert
        self.assertEqual(set(os.listdir(self.dest)), {"targetfile.txt", "symlinkfile.txt", "targetdir", "symlinkdir"})

        dest_symlink_file_path = os.path.join(self.dest, "symlinkfile.txt")
        self.assertTrue(os.path.islink(dest_symlink_file_path))
        self.assertEqual(os.readlink(dest_symlink_file_path), source_target_file_path)

        dest_symlink_dir_path = os.path.join(self.dest, "symlinkdir")
        self.assertTrue(os.path.islink(dest_symlink_dir_path))
        self.assertEqual(os.readlink(dest_symlink_dir_path), source_target_dir_path)

    def test_must_not_maintain_symlinks_by_default(self):
        # set up symlinked file and directory
        source_target_file_path = file(self.source, "targetfile.txt")
        source_symlink_file_path = os.path.join(self.source, "symlinkfile.txt")
        os.symlink(source_target_file_path, source_symlink_file_path)

        source_target_dir_path = os.path.join(self.source, "targetdir")
        os.makedirs(source_target_dir_path)
        file(source_target_dir_path, "file_in_dir.txt")
        source_symlink_dir_path = os.path.join(self.source, "symlinkdir")
        os.symlink(source_target_dir_path, source_symlink_dir_path)

        # call copytree
        copytree(self.source, self.dest)

        # assert
        self.assertEqual(set(os.listdir(self.dest)), {"targetfile.txt", "symlinkfile.txt", "targetdir", "symlinkdir"})

        dest_symlink_file_path = os.path.join(self.dest, "symlinkfile.txt")
        self.assertFalse(os.path.islink(dest_symlink_file_path))

        dest_symlink_dir_path = os.path.join(self.dest, "symlinkdir")
        self.assertFalse(os.path.islink(dest_symlink_dir_path))
        self.assertEqual(os.listdir(dest_symlink_dir_path), os.listdir(source_target_dir_path))


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


def file(*args):
    path = os.path.join(*args)
    basedir = os.path.dirname(path)
    if not os.path.exists(basedir):
        os.makedirs(basedir)

    # empty file
    open(path, "a").close()

    return path
