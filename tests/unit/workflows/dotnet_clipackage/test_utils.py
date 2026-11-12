import os
import platform
import stat
import tempfile
from unittest import TestCase, skipIf
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from aws_lambda_builders.workflows.dotnet_clipackage.utils import OSUtils


class TestDotnetCliPackageWorkflow(TestCase):
    def test_unzip_keeps_execute_permission_on_linux(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory(dir=temp_dir) as output_dir:
                test_file_name = "myFileToZip"
                path_to_file_to_zip = os.path.join(temp_dir, test_file_name)
                path_to_zip_file = os.path.join(temp_dir, "myZip.zip")
                expected_output_file = os.path.join(output_dir, test_file_name)
                with open(path_to_file_to_zip, "a") as the_file:
                    the_file.write("Hello World!")

                # Set execute permissions on the file before zipping (won't do anything on Windows)
                st = os.stat(path_to_file_to_zip)
                os.chmod(path_to_file_to_zip, st.st_mode | stat.S_IEXEC | stat.S_IXOTH | stat.S_IXGRP)

                # Zip the file
                with ZipFile(path_to_zip_file, "w") as myzip:
                    myzip.write(path_to_file_to_zip, test_file_name)

                # Unzip the file
                OSUtils().unzip(path_to_zip_file, output_dir)
                self.assertTrue(os.path.exists(expected_output_file))

                # Assert that execute permissions are still applied
                self.assertTrue(os.access(expected_output_file, os.X_OK))

    @skipIf(platform.system().lower() == "windows", "Creating symlinks requires extra privileges on Windows")
    @patch.dict("aws_lambda_builders.utils.os.environ", {}, clear=True)
    @patch("aws_lambda_builders.utils.locale.getencoding", create=True, return_value="ANSI_X3.4-1968")
    def test_unzip_keeps_non_ascii_symlink_target_under_c_locale(self, _):
        # Under the C/POSIX locale the locale encoding is ASCII; the UTF-8 symlink target must still be
        # decoded as UTF-8, otherwise the link points to a mangled (non-existent) path
        target_name = "caf\u00e9.txt"
        with tempfile.TemporaryDirectory() as temp_dir:
            path_to_zip_file = os.path.join(temp_dir, "myZip.zip")
            output_dir = os.path.join(temp_dir, "out")
            with ZipFile(path_to_zip_file, "w") as myzip:
                myzip.writestr(target_name, "Hello World!")
                link_info = ZipInfo("link")
                link_info.create_system = 3  # Unix
                link_info.external_attr = (stat.S_IFLNK | 0o777) << 16
                myzip.writestr(link_info, target_name.encode("utf-8"))

            OSUtils().unzip(path_to_zip_file, output_dir)

            link = os.path.join(output_dir, "link")
            self.assertEqual(os.readlink(link), target_name)
            self.assertTrue(os.path.exists(link))
