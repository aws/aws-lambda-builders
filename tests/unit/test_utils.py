import platform

from unittest import TestCase
from unittest.mock import patch

from aws_lambda_builders import utils
from aws_lambda_builders.utils import decode


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


class TestDecode(TestCase):
    def test_does_not_crash_non_utf8_encoding(self):
        message = "hello\n\n ß".encode("iso-8859-1")
        # Windows will decode this string as expected, *nix systems won't
        expected_message = "hello\n\n ß" if platform.system().lower() == "windows" else "hello\n\n �"
        response = decode(message)
        self.assertEqual(response, expected_message)

    def test_is_able_to_decode_non_utf8_encoding(self):
        message = "hello\n\n ß".encode("iso-8859-1")
        response = decode(message, "iso-8859-1")
        self.assertEqual(response, "hello\n\n ß")

    @patch("aws_lambda_builders.utils.locale")
    def test_is_able_to_decode_non_utf8_locale(self, mock_locale):
        mock_locale.getpreferredencoding.return_value = "iso-8859-1"
        message = "hello\n\n ß".encode("iso-8859-1")
        response = decode(message)
        self.assertEqual(response, "hello\n\n ß")

    def test_succeeds_with_utf8_encoding(self):
        message = "hello".encode("utf-8")
        response = decode(message)
        self.assertEqual(response, "hello")
