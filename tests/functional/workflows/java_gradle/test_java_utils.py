import os
import sys
import tempfile

from unittest import TestCase

from aws_lambda_builders.workflows.java_gradle import utils


class TestOSUtils(TestCase):

    def setUp(self):
        self.src = tempfile.mkdtemp()
        self.dst = tempfile.mkdtemp()
        self.os_utils = utils.OSUtils()

    def test_popen_runs_a_process_and_returns_outcome(self):
        cwd_py = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'cwd.py')
        p = self.os_utils.popen([sys.executable, cwd_py],
                                stdout=self.os_utils.pipe,
                                stderr=self.os_utils.pipe)
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode('utf8').strip(), os.getcwd())

    def test_popen_can_accept_cwd(self):
        testdata_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata')
        p = self.os_utils.popen([sys.executable, 'cwd.py'],
                                stdout=self.os_utils.pipe,
                                stderr=self.os_utils.pipe,
                                cwd=testdata_dir)
        out, err = p.communicate()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out.decode('utf8').strip(), os.path.abspath(testdata_dir))

    def test_listdir(self):
        names = ['a', 'b', 'c']
        for n in names:
            self.new_file(self.src, n)
        self.assertEquals(set(names), set(self.os_utils.listdir(self.src)))

    def test_copy(self):
        f = self.new_file(self.src, 'a')
        expected = os.path.join(self.dst, 'a')
        copy_ret = self.os_utils.copy(f, expected)
        self.assertEquals(expected, copy_ret)
        self.assertTrue('a' in os.listdir(self.dst))

    def test_exists(self):
        self.new_file(self.src, 'foo')
        self.assertTrue(self.os_utils.exists(os.path.join(self.src, 'foo')))

    def new_file(self, d, name):
        p = os.path.join(d, name)
        with open(p, 'w') as f:
            f.close()
        return p
