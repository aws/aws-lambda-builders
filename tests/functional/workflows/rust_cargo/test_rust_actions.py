import os
import shutil
import sys
import tempfile
import subprocess

from unittest import TestCase

from aws_lambda_builders.workflows.rust_cargo.actions import OSUtils


class TestOSUtils(TestCase):

    def test_popen_runs_a_process_and_returns_outcome(self):
        cwd_py = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "cwd.py")
        p = OSUtils().popen([sys.executable, cwd_py], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.getcwd())

    def test_popen_can_accept_cwd(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata")
        p = OSUtils().popen(
            [sys.executable, "cwd.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=testdata_dir
        )
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode("utf8").strip(), os.path.abspath(testdata_dir))
