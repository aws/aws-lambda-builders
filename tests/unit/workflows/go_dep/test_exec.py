from unittest import TestCase
from mock import patch

from aws_lambda_builders.workflows.go_dep.subproc_exec import SubprocessExec, ExecutionError


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessExec(TestCase):

    @patch("aws_lambda_builders.workflows.go_dep.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.under_test = SubprocessExec(self.osutils, "bin")

    def test_run_executes_bin_on_nixes(self):
        self.osutils.is_windows.side_effect = [False]

        self.under_test.run(["did", "thing"])

        self.osutils.popen.assert_called_with(["bin", "did", "thing"], cwd=None, env=None, stderr="PIPE", stdout="PIPE")

    def test_uses_cwd_if_supplied(self):
        self.under_test.run(["did", "thing"], cwd="/a/cwd")

        self.osutils.popen.assert_called_with(["bin", "did", "thing"],
                                              cwd="/a/cwd", env=None, stderr="PIPE", stdout="PIPE")

    def test_uses_env_if_supplied(self):
        self.under_test.run(["did", "thing"], env={"foo": "bar"})

        self.osutils.popen.assert_called_with(["bin", "did", "thing"],
                                              cwd=None, env={"foo": "bar"}, stderr="PIPE", stdout="PIPE")

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = "some encoded text\n\n"

        result = self.under_test.run(["did"])

        self.assertEqual(result, "some encoded text")

    def test_raises_ExecutionError_with_err_text_if_retcode_is_not_0(self):
        self.popen.returncode = 1
        self.popen.err = "some error text\n\n"

        with self.assertRaises(ExecutionError) as raised:
            self.under_test.run(["did"])

        self.assertEqual(raised.exception.args[0], "Exec Failed: some error text")

    def test_raises_ValueError_if_args_not_a_list(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run(("pack"))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")
