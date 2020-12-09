import os
import sys

from unittest import TestCase

from aws_lambda_builders.workflows.custom_make import utils


class TestOSUtils(TestCase):
    def setUp(self):

        self.osutils = utils.OSUtils()

    def test_popen_runs_a_process_and_returns_outcome(self):

        cwd_py = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "cwd.py")

        p = self.osutils.popen([sys.executable, cwd_py], stdout=self.osutils.pipe, stderr=self.osutils.pipe)

        out, err = p.communicate()

        self.assertEqual(p.returncode, 0)

        self.assertEqual(out.decode("utf8").strip(), os.getcwd())

    def test_popen_can_accept_cwd_and_env(self):

        testdata_dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata")
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
