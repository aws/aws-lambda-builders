from unittest import TestCase
from unittest.mock import patch

from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm, NpmExecutionError


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessNpm(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.under_test = SubprocessNpm(self.osutils, npm_exe="/a/b/c/npm.exe")

    def test_run_executes_npm_on_nixes(self):
        self.osutils.is_windows.side_effect = [False]

        self.under_test = SubprocessNpm(self.osutils)

        self.under_test.run(["pack", "-q"])

        self.osutils.popen.assert_called_with(["npm", "pack", "-q"], cwd=None, stderr="PIPE", stdout="PIPE")

    def test_run_executes_npm_cmd_on_windows(self):
        self.osutils.is_windows.side_effect = [True]

        self.under_test = SubprocessNpm(self.osutils)

        self.under_test.run(["pack", "-q"])

        self.osutils.popen.assert_called_with(["npm.cmd", "pack", "-q"], cwd=None, stderr="PIPE", stdout="PIPE")

    def test_uses_custom_npm_path_if_supplied(self):
        self.under_test.run(["pack", "-q"])

        self.osutils.popen.assert_called_with(["/a/b/c/npm.exe", "pack", "-q"], cwd=None, stderr="PIPE", stdout="PIPE")

    def test_uses_cwd_if_supplied(self):
        self.under_test.run(["pack", "-q"], cwd="/a/cwd")

        self.osutils.popen.assert_called_with(
            ["/a/b/c/npm.exe", "pack", "-q"], cwd="/a/cwd", stderr="PIPE", stdout="PIPE"
        )

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = b"some encoded text\n\n"

        result = self.under_test.run(["pack"])

        self.assertEqual(result, "some encoded text")

    def test_raises_NpmExecutionError_with_err_text_if_retcode_is_not_0(self):
        self.popen.returncode = 1
        self.popen.err = b"some error text\n\n"

        with self.assertRaises(NpmExecutionError) as raised:
            self.under_test.run(["pack"])

        self.assertEqual(raised.exception.args[0], "NPM Failed: some error text")

    def test_raises_ValueError_if_args_not_a_list(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run(("pack"))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")


class TestSubprocessNpmResolveProjectRoot(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.under_test = SubprocessNpm(self.osutils, npm_exe="npm")

    def test_asks_npm_for_the_prefix_and_strips_the_trailing_newline(self):
        self.osutils.popen.side_effect = [FakePopen(out=b"/repo\n")]

        self.assertEqual(self.under_test.resolve_project_root("/repo/endpoints/a"), "/repo")
        self.osutils.popen.assert_called_with(["npm", "prefix"], cwd="/repo/endpoints/a", stderr="PIPE", stdout="PIPE")

    def test_asks_npm_once_per_directory(self):
        # both the lockfile lookup and the artifacts link need this answer for the same directory, and
        # every extra call is another npm process in a build that already runs one per function
        self.osutils.popen.side_effect = [FakePopen(out=b"/repo\n")]

        self.assertEqual(self.under_test.resolve_project_root("/repo/endpoints/a"), "/repo")
        self.assertEqual(self.under_test.resolve_project_root("/repo/endpoints/a"), "/repo")

        self.assertEqual(self.osutils.popen.call_count, 1)

    def test_asks_again_for_a_different_directory(self):
        self.osutils.popen.side_effect = [FakePopen(out=b"/repo\n"), FakePopen(out=b"/other\n")]

        self.assertEqual(self.under_test.resolve_project_root("/repo/endpoints/a"), "/repo")
        self.assertEqual(self.under_test.resolve_project_root("/other"), "/other")

    def test_returns_none_when_npm_fails(self):
        self.osutils.popen.side_effect = [FakePopen(err=b"boom!", retcode=1)]

        self.assertIsNone(self.under_test.resolve_project_root("/repo/endpoints/a"))

    def test_caches_the_failure_too(self):
        # a second npm process would fail the same way; the caller falls back either way
        self.osutils.popen.side_effect = [FakePopen(err=b"boom!", retcode=1)]

        self.assertIsNone(self.under_test.resolve_project_root("/repo/endpoints/a"))
        self.assertIsNone(self.under_test.resolve_project_root("/repo/endpoints/a"))

        self.assertEqual(self.osutils.popen.call_count, 1)
