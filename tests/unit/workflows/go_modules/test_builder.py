from unittest import TestCase

from mock import patch, Mock

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflows.go_modules.builder import GoModulesBuilder, BuilderError


class FakePopen:
    def __init__(self, out=b'out', err=b'err', retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestGoBuilder(TestCase):

    @patch("aws_lambda_builders.workflows.go_modules.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = 'PIPE'
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.binaries = {
            "go": BinaryPath(resolver=Mock(), validator=Mock(),
                             binary="go", binary_path="/path/to/go")
        }
        self.under_test = GoModulesBuilder(self.osutils, self.binaries)

    def test_run_executes_bundler_on_nixes(self):
        self.osutils.is_windows.side_effect = [False]
        self.under_test = GoModulesBuilder(self.osutils, self.binaries)
        self.under_test.build("source_dir", "output_path")
        self.osutils.popen.assert_called_with(
            ["/path/to/go", "build", "-o", "output_path", "source_dir"],
            cwd="source_dir",
            env={'GOOS': 'linux', 'GOARCH': 'amd64'},
            stderr='PIPE',
            stdout='PIPE',
        )

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = b'some encoded text\n\n'
        result = self.under_test.build("source_dir", "output_path")
        self.assertEqual(result, 'some encoded text')

    def test_raises_BuilderError_with_err_text_if_retcode_is_not_0(self):
        self.popen.returncode = 1
        self.popen.err = b'some error text\n\n'
        with self.assertRaises(BuilderError) as raised:
            self.under_test.build("source_dir", "output_path")
        self.assertEqual(raised.exception.args[0], "Builder Failed: some error text")
