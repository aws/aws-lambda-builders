import os
import sys

from unittest import TestCase

from aws_lambda_builders.workflows.go_modules import utils


class TestOSUtils(TestCase):
    def setUp(self):
        self.osutils = utils.OSUtils()

    def test_environ_returns_environment(self):
        result = self.osutils.environ
        self.assertEqual(result, os.environ)

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
