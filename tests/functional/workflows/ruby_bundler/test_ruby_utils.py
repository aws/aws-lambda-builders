import os
import shutil
import sys
import tempfile

from unittest import TestCase

from aws_lambda_builders.workflows.ruby_bundler import utils


class TestOSUtils(TestCase):
    def setUp(self):
        self.osutils = utils.OSUtils()

    def test_extract_tarfile_unpacks_a_tar(self):
        test_tar = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        self.osutils.extract_tarfile(test_tar, test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_dirname_returns_directory_for_path(self):
        dirname = self.osutils.dirname(sys.executable)
        self.assertEqual(dirname, os.path.dirname(sys.executable))

    def test_abspath_returns_absolute_path(self):
        result = self.osutils.abspath(".")
        self.assertTrue(os.path.isabs(result))
        self.assertEqual(result, os.path.abspath("."))

    def test_joinpath_joins_path_components(self):
        result = self.osutils.joinpath("a", "b", "c")
        self.assertEqual(result, os.path.join("a", "b", "c"))

    def test_popen_runs_a_process_and_returns_outcome(self):
        cwd_py = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "cwd.py")
        p = self.osutils.popen([sys.executable, cwd_py], stdout=self.osutils.pipe, stderr=self.osutils.pipe)
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.getcwd())

    def test_popen_can_accept_cwd(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata")
        p = self.osutils.popen(
            [sys.executable, "cwd.py"], stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=testdata_dir
        )
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.path.abspath(testdata_dir))

    def test_returns_true_if_directory_exists(self):
        testdata_dir = os.path.dirname(__file__)
        out = self.osutils.directory_exists(testdata_dir)
        self.assertTrue(out)

    def test_returns_false_if_directory_not_found(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), "test")
        out = self.osutils.directory_exists(testdata_dir)
        self.assertFalse(out)

    def test_returns_bundle_directory(self):
        testdata_dir = os.path.dirname(__file__)
        out = self.osutils.get_bundle_dir(testdata_dir)
        self.assertEqual(out, os.path.join(os.path.dirname(__file__), ".bundle"))

    def test_removes_directory_if_exists(self):
        test_dir = tempfile.mkdtemp()
        bundle_dir = os.path.join(test_dir, ".bundle")
        expected_files = set(os.listdir(test_dir))
        os.mkdir(bundle_dir)
        self.osutils.remove_directory(bundle_dir)
        actual_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual(actual_files, expected_files)
