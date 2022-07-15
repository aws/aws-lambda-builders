from unittest import TestCase
from unittest.mock import patch

from aws_lambda_builders import utils


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
