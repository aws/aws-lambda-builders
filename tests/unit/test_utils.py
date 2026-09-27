import os
import platform
import tempfile
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
        # Without this the mocked Path makes the already-a-symlink branch truthy and the function
        # returns before it ever calls os.symlink.
        patched_path.return_value.exists.return_value = False

        source_path = "source/path"
        destination_path = "destination/path"
        utils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_called_once()
        patched_copy_tree.assert_called_with(source_path, destination_path)

    @patch("aws_lambda_builders.utils.Path")
    @patch("aws_lambda_builders.utils.os")
    @patch("aws_lambda_builders.utils.copytree")
    def test_must_not_copy_when_symlink_succeeds(self, patched_copy_tree, pathced_os, patched_path):
        source_path = "source/path"
        destination_path = "destination/path"
        utils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_not_called()
        patched_copy_tree.assert_not_called()

    def test_falls_back_to_copying_a_top_level_file(self):
        # A dependencies directory holds files as well as packages, and copytree cannot copy a file.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "six.py")
            source.write_text("body")
            destination = Path(tmp, "artifacts", "six.py")

            with patch("aws_lambda_builders.utils.os.symlink", side_effect=OSError("privilege not held")):
                utils.create_symlink_or_copy(str(source), str(destination))

            self.assertTrue(destination.is_file())
            self.assertEqual(destination.read_text(), "body")

    def test_falls_back_to_copying_a_package_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "somepkg")
            source.mkdir()
            (source / "__init__.py").write_text("body")
            destination = Path(tmp, "artifacts", "somepkg")

            with patch("aws_lambda_builders.utils.os.symlink", side_effect=OSError("privilege not held")):
                utils.create_symlink_or_copy(str(source), str(destination))

            self.assertTrue(destination.is_dir())
            self.assertEqual((destination / "__init__.py").read_text(), "body")


class Test_copytree(TestCase):
    def test_does_not_write_through_a_symlinked_destination(self):
        """A linking build leaves symlinks into the shared dependencies directory. Copying the
        source tree over a colliding name must stay inside the destination tree rather than
        following the link and mutating a cache that later builds reuse."""
        with tempfile.TemporaryDirectory() as tmp:
            deps = Path(tmp, "deps", "requests")
            deps.mkdir(parents=True)
            (deps / "__init__.py").write_text("dependency")

            artifacts = Path(tmp, "artifacts")
            artifacts.mkdir()
            os.symlink(str(deps), str(artifacts / "requests"))

            source = Path(tmp, "source", "requests")
            source.mkdir(parents=True)
            (source / "my_helper.py").write_text("user code")

            utils.copytree(str(Path(tmp, "source")), str(artifacts))

            self.assertFalse((deps / "my_helper.py").exists(), "source leaked into the dependencies directory")
            self.assertFalse((artifacts / "requests").is_symlink())
            self.assertEqual((artifacts / "requests" / "my_helper.py").read_text(), "user code")
            self.assertEqual((artifacts / "requests" / "__init__.py").read_text(), "dependency")


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
