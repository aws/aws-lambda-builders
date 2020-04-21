from unittest import TestCase
from mock import patch

from aws_lambda_builders.workflows.custom_make.make import MakeExecutionError, SubProcessMake


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessMake(TestCase):
    @patch("aws_lambda_builders.workflows.custom_make.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.under_test = SubProcessMake(self.osutils, make_exe="/a/b/c/make.exe")

    def test_run_executes_make_on_nixes(self):
        self.osutils.is_windows.side_effect = [False]

        self.under_test = SubProcessMake(self.osutils)

        self.under_test.run(["build-logical_id"])

        self.osutils.popen.assert_called_with(
            ["make", "build-logical_id"], cwd=None, env=None, stderr="PIPE", stdout="PIPE"
        )

    def test_run_executes_make_cmd_on_windows(self):
        self.osutils.is_windows.side_effect = [True]

        self.under_test = SubProcessMake(self.osutils)

        self.under_test.run(["build-logical_id"])

        self.osutils.popen.assert_called_with(
            ["make.exe", "build-logical_id"], cwd=None, env=None, stderr="PIPE", stdout="PIPE"
        )

    def test_uses_custom_make_path_if_supplied(self):
        self.under_test.run(["build_logical_id"])

        self.osutils.popen.assert_called_with(
            ["/a/b/c/make.exe", "build_logical_id"], cwd=None, env=None, stderr="PIPE", stdout="PIPE"
        )

    def test_uses_cwd_if_supplied(self):
        self.under_test.run(["build_logical_id"], cwd="/a/cwd")

        self.osutils.popen.assert_called_with(
            ["/a/b/c/make.exe", "build_logical_id"], cwd="/a/cwd", env=None, stderr="PIPE", stdout="PIPE"
        )

    def test_uses_env_and_cwd_if_supplied(self):
        self.under_test.run(["build_logical_id"], cwd="/a/cwd", env={"a": "b"})

        self.osutils.popen.assert_called_with(
            ["/a/b/c/make.exe", "build_logical_id"], cwd="/a/cwd", env={"a": "b"}, stderr="PIPE", stdout="PIPE"
        )

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = b"some encoded text\n\n"

        result = self.under_test.run(["build_logical_id"])

        self.assertEqual(result, "some encoded text")

    def test_raises_MakeExecutionError_with_err_text_if_retcode_is_not_0(self):
        self.popen.returncode = 1
        self.popen.err = b"some error text\n\n"

        with self.assertRaises(MakeExecutionError) as raised:
            self.under_test.run(["build-logical_id"])

        self.assertEqual(raised.exception.args[0], "Make Failed: some error text")

    def test_raises_ValueError_if_args_not_a_list(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run(("build-logical_id"))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")
