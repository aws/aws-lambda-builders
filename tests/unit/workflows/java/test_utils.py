import os
import shutil
import tempfile
from contextlib import contextmanager
from unittest import TestCase

from aws_lambda_builders.workflows.java.utils import OSUtils


@contextmanager
def mkdir_temp(mode=0o755, ignore_errors=False):
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        os.chmod(temp_dir, mode)

        yield temp_dir

    finally:
        if temp_dir:
            if ignore_errors:
                shutil.rmtree(temp_dir, False)
            else:
                shutil.rmtree(temp_dir)


class TestOSUtils(TestCase):
    def test_copyjars(self):
        self.os_utils = OSUtils()
        with mkdir_temp() as src_dir:
            with mkdir_temp() as dst_dir:
                try:
                    tmpfile = tempfile.mktemp(".jar", "temp", src_dir)
                    f = open(tmpfile, "a")
                    f.write("jar file")
                    f.close()
                    self.os_utils.copyjars(src_dir, dst_dir)
                    self.assertTrue(self.os_utils.exists(os.path.join(dst_dir, tmpfile)))
                except:
                    self.fail("error occurred during test")
