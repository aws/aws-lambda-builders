import os
import shutil
import sys
import tempfile

from unittest import TestCase

from aws_lambda_builders.workflows.ruby_bundler import utils


class TestOSUtils(TestCase):
    def setUp(self):
        self.osutils = utils.RubyOSUtils()

    def test_extract_tarfile_unpacks_a_tar(self):
        test_tar = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        self.osutils.extract_tarfile(test_tar, test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_returns_bundle_directory(self):
        testdata_dir = os.path.dirname(__file__)
        out = self.osutils.get_bundle_dir(testdata_dir)
        self.assertEqual(out, os.path.join(os.path.dirname(__file__), ".bundle"))
