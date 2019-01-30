from unittest import TestCase

from mock import patch, Mock
from parameterized import parameterized
from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.workflows.java_gradle.validators import GradleBinaryValidator, JavaRuntimeValidator


class FakePopen(object):
    def __init__(self, stdout=None, stderr=None, returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode

    def communicate(self):
        return self._stdout, self._stderr

    @property
    def returncode(self):
        return self._returncode


class TestGradleBinaryValidator(TestCase):

    def setUp(self):
        self._validator = GradleBinaryValidator()

    def test_validate(self):
        # the validator is no-op at the moment
        runtime_path = '/path/to/gradle'
        self._validator.validate(runtime_path)
        self.assertEqual(self._validator.validated_runtime_path, runtime_path)


class TestJavaRuntimeValidator(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.mock_os_utils = MockOSUtils.return_value

    @parameterized.expand([
        'java',
        'java8'
    ])
    def test_supported_runtimes(self, runtime):
        validator = JavaRuntimeValidator(runtime=runtime)
        self.assertTrue(validator.has_runtime())

    def test_runtime_validate_unsupported_language_fail_open(self):
        validator = JavaRuntimeValidator(runtime='java11')
        self.assertFalse(validator.validate(runtime_path='/usr/bin/java11'))

    @parameterized.expand([
        '1.7.0',
        '1.8.9',
        '11.0.0'
    ])
    def test_java_runtime_accepts_any_major_version(self, version):
        version_string = ('java version "%s"' % version).encode()
        runtime_path = '/path/to/java'
        self.mock_os_utils.popen.side_effect = [FakePopen(stderr=version_string)]
        validator = JavaRuntimeValidator(runtime='java', os_utils=self.mock_os_utils)
        self.assertTrue(validator.validate(runtime_path=runtime_path))
        self.assertEqual(validator.validated_runtime_path, runtime_path)

    def test_emits_warning_when_mv_greater_than_8(self):
        version_string = 'java version "9.0.0"'.encode()
        runtime_path = '/path/to/java'
        mock_log = Mock()
        self.mock_os_utils.popen.side_effect = [FakePopen(stderr=version_string)]
        validator = JavaRuntimeValidator(runtime='java', os_utils=self.mock_os_utils, log=mock_log)
        self.assertTrue(validator.validate(runtime_path=runtime_path))
        self.assertEqual(validator.validated_runtime_path, runtime_path)
        mock_log.warning.assert_called_with(JavaRuntimeValidator.MAJOR_VERSION_WARNING, runtime_path, '9')

    @parameterized.expand([
        '1.6.0',
        '1.7.0',
        '1.8.9'
    ])
    def test_does_not_emit_warning_when_mv_8_or_less(self, version):
        version_string = ('java version "%s"' % version).encode()
        runtime_path = '/path/to/java'
        mock_log = Mock()
        self.mock_os_utils.popen.side_effect = [FakePopen(stderr=version_string)]
        validator = JavaRuntimeValidator(runtime='java', os_utils=self.mock_os_utils, log=mock_log)
        self.assertTrue(validator.validate(runtime_path=runtime_path))
        self.assertEqual(validator.validated_runtime_path, runtime_path)
        mock_log.warning.assert_not_called()

    def test_java_executable_fails(self):
        version_string = 'java version "1.8.0"'.encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stderr=version_string, returncode=1)]
        validator = JavaRuntimeValidator(runtime='java8', os_utils=self.mock_os_utils)
        with self.assertRaises(MisMatchRuntimeError) as raised:
            validator.validate(runtime_path='/path/to/java')
        self.assertTrue(raised.exception.args[0].startswith('java executable found in your path'))
