import os
import shutil
import sys
import tempfile
from unittest import TestCase

from aws_lambda_builders.os_utils import OSUtils


class TestOSUtils(TestCase):
    def setUp(self):
        self.src = tempfile.mkdtemp()
        self.dst = tempfile.mkdtemp()
        self.osutils = OSUtils()

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
        cwd_py = os.path.join(os.path.dirname(__file__), "test_data", "cwd.py")
        p = self.osutils.popen([sys.executable, cwd_py], stdout=self.osutils.pipe, stderr=self.osutils.pipe)
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.getcwd())

    def test_popen_can_accept_cwd(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), "test_data")
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

    def test_removes_directory_if_exists(self):
        test_dir = tempfile.mkdtemp()
        bundle_dir = os.path.join(test_dir, ".bundle")
        expected_files = set(os.listdir(test_dir))
        os.mkdir(bundle_dir)
        self.osutils.remove_directory(bundle_dir)
        actual_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual(actual_files, expected_files)

    def test_popen_can_accept_cwd_and_env(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), "test_data")
        env = os.environ.copy()
        env.update({"SOME_ENV": "SOME_VALUE"})

        p = self.osutils.popen(
            [sys.executable, "cwd.py"],
            stdout=self.osutils.pipe,
            stderr=self.osutils.pipe,
            env=env,
            cwd=testdata_dir,
        )

        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.path.abspath(testdata_dir))

    def test_extract_tarfile_unpacks_a_tar(self):
        test_tar = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        self.osutils.extract_tarfile(test_tar, test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_copy_file_copies_existing_file_into_a_dir(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        self.osutils.copy_file(test_file, test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test.tgz"}, output_files)

    def test_copy_file_copies_existing_file_into_a_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        self.osutils.copy_file(test_file, os.path.join(test_dir, "copied_test.tgz"))
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"copied_test.tgz"}, output_files)

    def test_remove_file_removes_existing_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        test_dir = tempfile.mkdtemp()
        copied_file = os.path.join(test_dir, "copied_test.tgz")
        shutil.copy(test_file, copied_file)
        self.osutils.remove_file(copied_file)
        self.assertFalse(os.path.isfile(copied_file))

    def test_file_exists_checking_if_file_exists_in_a_dir(self):
        existing_file = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")
        nonexisting_file = os.path.join(os.path.dirname(__file__), "test_data", "nonexisting.tgz")
        self.assertTrue(self.osutils.file_exists(existing_file))
        self.assertFalse(self.osutils.file_exists(nonexisting_file))

    def test_parse_json_reads_json_contents_into_memory(self):
        json_file = os.path.join(os.path.dirname(__file__), "test_data", "test.json")
        json_contents = self.osutils.parse_json(json_file)
        self.assertEqual(json_contents["a"], 1)
        self.assertEqual(json_contents["b"]["c"], 2)

    def test_listdir(self):
        names = ["a", "b", "c"]
        for n in names:
            self.new_file(self.src, n)
        self.assertEqual(set(names), set(self.osutils.listdir(self.src)))

    def test_copy(self):
        f = self.new_file(self.src, "a")
        expected = os.path.join(self.dst, "a")
        copy_ret = self.osutils.copy(f, expected)
        self.assertEqual(expected, copy_ret)
        self.assertTrue("a" in os.listdir(self.dst))

    def test_exists(self):
        self.new_file(self.src, "foo")
        self.assertTrue(self.osutils.exists(os.path.join(self.src, "foo")))

    def new_file(self, d, name):
        p = os.path.join(d, name)
        with open(p, "w") as f:
            f.close()
        return p
