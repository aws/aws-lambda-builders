from unittest import TestCase
from mock import patch

from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm, NpmExecutionError, NpmModulesUtils


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


class TestNpmModulesUtils(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def setUp(self, OSUtilMock, SubprocessNpmMock):

        self.osutils = OSUtilMock.return_value
        self.subprocess_npm = SubprocessNpmMock.return_value
        self.under_test = NpmModulesUtils(self.osutils, self.subprocess_npm, 'scratch_dir')

    def test_get_local_dependencies_reads_package_json(self):
        self.osutils.get_text_contents.side_effect = ['{}']
        self.osutils.joinpath.side_effect = ['joined/path']

        self.under_test.get_local_dependencies('some/dir')

        self.osutils.get_text_contents.assert_called_with('joined/path')
        self.osutils.joinpath.assert_called_with('some/dir', 'package.json')

    def test_get_local_dependencies_returns_empty_dict_when_no_dependencies(self):
        self.osutils.get_text_contents.side_effect = ['{}']

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {})

    def test_get_local_dependencies_returns_empty_dict_whitout_local_dependencies(self):
        self.osutils.get_text_contents.side_effect = ['{"dependencies":{"claudia":"*"}}']

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {})

    def test_get_local_dependencies_return_dict_with_local_dependencies(self):
        self.osutils.get_text_contents.side_effect = ['{"dependencies":{"claudia":"file:/claudia/"}}']

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {'claudia': 'file:/claudia/'})

    def test_get_local_dependencies_filters_only_local_dependencies(self):
        self.osutils.get_text_contents.side_effect = [
            '{"dependencies":{"claudia":"*","aws-sdk":"*","foo":"file:/foo","bar":"./bar","baz":"/baz"}}'
        ]

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {'foo': 'file:/foo', 'bar': './bar', 'baz': '/baz'})

    def test_get_local_dependencies_from_a_defined_key(self):
        self.osutils.get_text_contents.side_effect = ['{"optionalDependencies":{"claudia":"file:/claudia/"}}']

        result = self.under_test.get_local_dependencies('some/dir', 'optionalDependencies')

        self.assertEqual(result, {'claudia': 'file:/claudia/'})
