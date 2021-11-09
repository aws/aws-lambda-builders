from unittest import TestCase
from mock import patch

from aws_lambda_builders.workflows.nodejs_npm.esbuild import SubprocessEsbuild, EsbuildExecutionError


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessEsbuild(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]

        which = lambda cmd, executable_search_paths: ["{}/{}".format(executable_search_paths[0], cmd)]

        self.under_test = SubprocessEsbuild(self.osutils, ["/a/b", "/c/d"], which)

    def test_run_executes_binary_found_in_exec_paths(self):

        self.under_test.run(["arg-a", "arg-b"])

        self.osutils.popen.assert_called_with(
            ["/a/b/esbuild", "arg-a", "arg-b"], cwd=None, stderr="PIPE", stdout="PIPE"
        )

    def test_uses_cwd_if_supplied(self):
        self.under_test.run(["arg-a", "arg-b"], cwd="/a/cwd")

        self.osutils.popen.assert_called_with(
            ["/a/b/esbuild", "arg-a", "arg-b"], cwd="/a/cwd", stderr="PIPE", stdout="PIPE"
        )

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = b"some encoded text\n\n"

        result = self.under_test.run(["pack"])

        self.assertEqual(result, "some encoded text")

    def test_raises_EsbuildExecutionError_with_err_text_if_retcode_is_not_0(self):
        self.popen.returncode = 1
        self.popen.err = b"some error text\n\n"

        with self.assertRaises(EsbuildExecutionError) as raised:
            self.under_test.run(["pack"])

        self.assertEqual(raised.exception.args[0], "Esbuild Failed: some error text")

    def test_raises_EsbuildExecutionError_if_which_returns_no_results(self):

        which = lambda cmd, executable_search_paths: []
        self.under_test = SubprocessEsbuild(self.osutils, ["/a/b", "/c/d"], which)
        with self.assertRaises(EsbuildExecutionError) as raised:
            self.under_test.run(["pack"])

        self.assertEqual(raised.exception.args[0], "Esbuild Failed: cannot find esbuild")

    def test_raises_ValueError_if_args_not_a_list(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run(("pack"))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")
