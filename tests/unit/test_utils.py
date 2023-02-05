import os
from unittest import TestCase
from unittest.mock import patch

from aws_lambda_builders import utils
from aws_lambda_builders.exceptions import FileOperationError


class Test_create_symlink_or_copy(TestCase):
    @patch("aws_lambda_builders.utils.Path")
    @patch("aws_lambda_builders.utils.os")
    @patch("aws_lambda_builders.utils.copytree")
    def test_must_create_symlink_with_absolute_path(self, patched_copy_tree, pathced_os, patched_path):
        source_path = "source/path"
        destination_path = "destination/path"
        utils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_called_with(
            patched_path(source_path).absolute(), patched_path(destination_path).absolute()
        )
        patched_copy_tree.assert_not_called()

    @patch("aws_lambda_builders.utils.Path")
    @patch("aws_lambda_builders.utils.os")
    @patch("aws_lambda_builders.utils.copytree")
    def test_must_copy_if_symlink_fails(self, patched_copy_tree, pathced_os, patched_path):
        pathced_os.symlink.side_effect = OSError("Unable to create symlink")

        source_path = "source/path"
        destination_path = "destination/path"
        utils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_called_once()
        patched_copy_tree.assert_called_with(source_path, destination_path)


class Test_glob_copy(TestCase):
    @patch("aws_lambda_builders.utils.glob")
    @patch("aws_lambda_builders.utils.os")
    def test_raises_error_dest_file_and_no_matches(self, patched_os, patched_glob):
        patched_os.path.split = os.path.split
        patched_glob.return_value = []
        self.assertRaisesRegex(
            FileOperationError, 'glob_copy - "test.txt" not found', utils.glob_copy, "test.txt", "dest"
        )
        patched_glob.assert_called_once_with("test.txt", recursive=True)

    @patch("aws_lambda_builders.utils.glob")
    @patch("aws_lambda_builders.utils.os")
    def test_sets_glob_recursive(self, patched_os, patched_glob):
        patched_os.path.split = os.path.split
        patched_glob.return_value = []
        self.assertRaisesRegex(
            FileOperationError, 'glob_copy - "test.txt" not found', utils.glob_copy, "test.txt", "dest", recursive=False
        )
        patched_glob.assert_called_once_with("test.txt", recursive=False)

    @patch("aws_lambda_builders.utils.glob")
    @patch("aws_lambda_builders.utils.os")
    @patch("aws_lambda_builders.utils.shutil")
    def test_saves_on_matches(self, patched_shutil, patched_os, patched_glob):
        source = os.path.join("foo", "test*.txt")
        dest = "dest"
        match1 = os.path.join("foo", "test1.txt")
        match2 = os.path.join("foo", "bar", "test2.txt")
        match3 = os.path.join("foo", "bar", "test3.txt")
        dest1 = os.path.join("dest", "test1.txt")
        dest2 = os.path.join("dest", "bar", "test2.txt")
        dest3 = os.path.join("dest", "bar", "test3.txt")
        dir1 = os.path.dirname(dest1)
        dir2 = os.path.dirname(dest2)

        patched_glob.return_value = [match1, match2, match3]
        patched_os.path.dirname = os.path.dirname
        patched_os.path.split = os.path.split
        patched_os.path.join = os.path.join
        patched_os.makedirs.return_value = None
        patched_shutil.copyfle.return_value = None

        utils.glob_copy(source, dest)
        patched_glob.assert_called_once_with(source, recursive=True)

        # Should only be called once for each directory
        self.assertEqual(2, patched_os.makedirs.call_count)
        self.assertEqual(dir1, patched_os.makedirs.mock_calls[0][1][0])
        self.assertEqual(dir2, patched_os.makedirs.mock_calls[1][1][0])

        self.assertEqual(3, patched_shutil.copyfile.call_count)
        self.assertEqual(match1, patched_shutil.copyfile.mock_calls[0][1][0])
        self.assertEqual(dest1, patched_shutil.copyfile.mock_calls[0][1][1])
        self.assertEqual(match2, patched_shutil.copyfile.mock_calls[1][1][0])
        self.assertEqual(dest2, patched_shutil.copyfile.mock_calls[1][1][1])
        self.assertEqual(match3, patched_shutil.copyfile.mock_calls[2][1][0])
        self.assertEqual(dest3, patched_shutil.copyfile.mock_calls[2][1][1])


class Test_get_option_from_args(TestCase):
    def test_returns_null_on_no_args(self):
        self.assertEqual(None, utils.get_option_from_args(None, "foo"))

    def test_returns_null_on_no_options(self):
        self.assertEqual(None, utils.get_option_from_args({}, "foo"))

    def test_returns_null_on_missing_option(self):
        self.assertEqual(None, utils.get_option_from_args({"options": {}}, "foo"))

    def test_returns_value_on_matching_option(self):
        self.assertEqual("bar", utils.get_option_from_args({"options": {"foo": "bar"}}, "foo"))
