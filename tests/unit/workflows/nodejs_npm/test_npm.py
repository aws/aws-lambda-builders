from unittest import TestCase
from mock import patch

from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm, NpmExecutionError


class FakePopen:
    def __init__(self, out=b'out', err=b'err', retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessNpm(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):

        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = 'PIPE'
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.under_test = SubprocessNpm(self.osutils, npm_exe="/a/b/c/npm.exe")

    def test_run_executes_npm_on_nixes(self):

        self.osutils.is_windows.side_effect = [False]

        self.under_test = SubprocessNpm(self.osutils)

        self.under_test.run(['pack', '-q'])

        self.osutils.popen.assert_called_with(['npm', 'pack', '-q'], cwd=None, stderr='PIPE', stdout='PIPE')

    def test_run_executes_npm_cmd_on_windows(self):

        self.osutils.is_windows.side_effect = [True]

        self.under_test = SubprocessNpm(self.osutils)

        self.under_test.run(['pack', '-q'])

        self.osutils.popen.assert_called_with(['npm.cmd', 'pack', '-q'], cwd=None, stderr='PIPE', stdout='PIPE')

    def test_uses_custom_npm_path_if_supplied(self):

        self.under_test.run(['pack', '-q'])

        self.osutils.popen.assert_called_with(['/a/b/c/npm.exe', 'pack', '-q'], cwd=None, stderr='PIPE', stdout='PIPE')

    def test_uses_cwd_if_supplied(self):

        self.under_test.run(['pack', '-q'], cwd='/a/cwd')

        self.osutils.popen.assert_called_with(['/a/b/c/npm.exe', 'pack', '-q'],
                                              cwd='/a/cwd', stderr='PIPE', stdout='PIPE')

    def test_returns_popen_out_decoded_if_retcode_is_0(self):

        self.popen.out = b'some encoded text\n\n'

        result = self.under_test.run(['pack'])

        self.assertEqual(result, 'some encoded text')

    def test_raises_NpmExecutionError_with_err_text_if_retcode_is_not_0(self):

        self.popen.returncode = 1
        self.popen.err = b'some error text\n\n'

        with self.assertRaises(NpmExecutionError) as raised:
            self.under_test.run(['pack'])

        self.assertEqual(raised.exception.args[0], "NPM Failed: some error text")

    def test_raises_ValueError_if_args_not_a_list(self):

        with self.assertRaises(ValueError) as raised:
            self.under_test.run(('pack'))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):

        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")
