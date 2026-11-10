import platform
from pathlib import Path

from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from aws_lambda_builders import utils
from aws_lambda_builders.utils import decode


class Test_create_symlink_or_copy(TestCase):
    @patch("aws_lambda_builders.utils.os")
    @patch("aws_lambda_builders.utils.copytree")
    def test_must_create_symlink_with_absolute_path(self, patched_copy_tree, patched_os):
        source_path = "source/path"
        destination_path = "destination/path"

        p = MagicMock()
        p.return_value = False

        with patch("aws_lambda_builders.utils.Path.is_symlink", p):
            utils.create_symlink_or_copy(source_path, destination_path)

        patched_os.symlink.assert_called_with(Path(source_path).absolute(), Path(destination_path).absolute())
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

    @patch("aws_lambda_builders.utils.Path")
    @patch("aws_lambda_builders.utils.os")
    @patch("aws_lambda_builders.utils.copytree")
    def test_must_copy_if_symlink_fails(self, patched_copy_tree, pathced_os, patched_path):
        source_path = "source/path"
        destination_path = "destination/path"
        utils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_not_called()
        patched_copy_tree.assert_not_called()


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

    def test_succeeds_with_utf8_encoding(self):
        message = "hello".encode("utf-8")
        response = decode(message)
        self.assertEqual(response, "hello")


@patch.dict("aws_lambda_builders.utils.os.environ", {}, clear=True)
@patch("aws_lambda_builders.utils.sys._xoptions", {})
@patch("aws_lambda_builders.utils.locale")
class TestDecodeLocaleEncoding(TestCase):
    LATIN1 = "hello\n\n ß".encode("iso-8859-1")
    UTF8 = "café ✓".encode("utf-8")

    def test_uses_locale_encoding(self, mock_locale):
        mock_locale.getencoding.return_value = "iso-8859-1"
        self.assertEqual(decode(self.LATIN1), "hello\n\n ß")

    def test_uses_locale_encoding_when_utf8_mode_is_on_by_default(self, mock_locale):
        # Python 3.15 enables UTF-8 mode by default (PEP 686): getpreferredencoding() reports
        # utf-8 while the locale (and the output of external tools) still uses another encoding
        mock_locale.getpreferredencoding.return_value = "utf-8"
        mock_locale.getencoding.return_value = "cp1252"
        self.assertEqual(decode(self.LATIN1), "hello\n\n ß")

    def test_ascii_c_locale_decodes_as_utf8(self, mock_locale):
        # C/POSIX locale: Python auto-enables UTF-8 mode (PEP 540) and the locale encoding is ASCII
        for ascii_name in ("ANSI_X3.4-1968", "US-ASCII", "ascii"):
            with self.subTest(ascii_name):
                mock_locale.getencoding.return_value = ascii_name
                self.assertEqual(decode(self.UTF8), "café ✓")

    def test_explicit_pythonutf8_env_decodes_as_utf8(self, mock_locale):
        mock_locale.getencoding.return_value = "cp1252"
        with patch.dict("aws_lambda_builders.utils.os.environ", {"PYTHONUTF8": "1"}):
            self.assertEqual(decode(self.UTF8), "café ✓")

    def test_pythonutf8_disabled_uses_locale_encoding(self, mock_locale):
        mock_locale.getencoding.return_value = "cp1252"
        with patch.dict("aws_lambda_builders.utils.os.environ", {"PYTHONUTF8": "0"}):
            self.assertEqual(decode(self.LATIN1), "hello\n\n ß")

    def test_explicit_x_utf8_option_decodes_as_utf8(self, mock_locale):
        mock_locale.getencoding.return_value = "cp1252"
        for value in (True, "1"):
            with self.subTest(value), patch("aws_lambda_builders.utils.sys._xoptions", {"utf8": value}):
                self.assertEqual(decode(self.UTF8), "café ✓")

    def test_unknown_locale_encoding_decodes_as_utf8(self, mock_locale):
        mock_locale.getencoding.return_value = "not-a-real-codec"
        self.assertEqual(decode(self.UTF8), "café ✓")

    def test_falls_back_to_preferred_encoding_without_getencoding(self, mock_locale):
        # locale.getencoding() only exists on Python 3.11+
        del mock_locale.getencoding
        mock_locale.getpreferredencoding.return_value = "iso-8859-1"
        self.assertEqual(decode(self.LATIN1), "hello\n\n ß")


class TestIsWithinDirectory(TestCase):
    def test_target_inside_directory(self):
        self.assertTrue(utils._is_within_directory("/my/path", "/my/path/file"))

    def test_directory_is_within_itself(self):
        self.assertTrue(utils._is_within_directory("/my/path", "/my/path"))

    def test_target_outside_directory(self):
        self.assertFalse(utils._is_within_directory("/my/path", "/another/path/file"))

    def test_sibling_directory_sharing_name_prefix_is_not_within(self):
        # "/my/pathological" shares a string prefix with "/my/path" but is not inside it
        self.assertFalse(utils._is_within_directory("/my/path", "/my/pathological/file"))

    def test_escaping_with_parent_reference_is_not_within(self):
        self.assertFalse(utils._is_within_directory("/my/path", "/my/path/../other/file"))

    @patch("aws_lambda_builders.utils.os.path.commonpath", side_effect=ValueError("different drives"))
    def test_paths_on_different_drives_are_not_within(self, _):
        self.assertFalse(utils._is_within_directory("C:\\my\\path", "D:\\file"))
