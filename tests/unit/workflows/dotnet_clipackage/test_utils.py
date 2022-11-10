import os
import stat
import tempfile
from unittest import TestCase
from zipfile import ZipFile

from aws_lambda_builders.workflows.dotnet_clipackage.utils import OSUtils


class TestDotnetCliPackageWorkflow(TestCase):

    def test_unzip_keeps_execute_permission_on_linux(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory(dir=temp_dir) as output_dir:
                test_file_name = 'myFileToZip'
                path_to_file_to_zip = os.path.join(temp_dir, test_file_name)
                path_to_zip_file = os.path.join(temp_dir, 'myZip.zip')
                expected_output_file = os.path.join(output_dir, test_file_name)
                with open(path_to_file_to_zip, 'a') as the_file:
                    the_file.write('Hello World!')

                # Set execute permissions on the file before zipping (won't do anything on Windows)
                st = os.stat(path_to_file_to_zip)
                os.chmod(path_to_file_to_zip, st.st_mode | stat.S_IEXEC | stat.S_IXOTH | stat.S_IXGRP)

                # Zip the file
                with ZipFile(path_to_zip_file, 'w') as myzip:
                    myzip.write(path_to_file_to_zip, test_file_name)

                # Unzip the file
                OSUtils().unzip(path_to_zip_file, output_dir)
                self.assertTrue(os.path.exists(expected_output_file))

                # Assert that execute permissions are still applied
                self.assertTrue(os.access(expected_output_file, os.X_OK))
