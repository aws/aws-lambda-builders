from unittest import TestCase

from mock import patch, Mock
from parameterized import parameterized
from aws_lambda_builders.workflows.java_gradle.gradle_validator import GradleBinaryValidator, GradleBinaryValidatorError


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

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.mock_os_utils = MockOSUtils.return_value

    @parameterized.expand([
        '1.7.0',
        '1.8.9',
        '11.0.0'
    ])
    def test_accepts_any_jvm_mv(self, version):
        version_string = ('JVM:          %s' % version).encode()
        gradle_path = '/path/to/gradle'
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils)
        self.assertTrue(validator.validate(gradle_path=gradle_path))
        self.assertEqual(validator.validated_binary_path, gradle_path)

    def test_emits_warning_when_jvm_mv_greater_than_8(self):
        version_string = 'JVM:          9.0.0'.encode()
        gradle_path = '/path/to/gradle'
        mock_log = Mock()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils, log=mock_log)
        self.assertTrue(validator.validate(gradle_path=gradle_path))
        self.assertEqual(validator.validated_binary_path, gradle_path)
        mock_log.warning.assert_called_with(GradleBinaryValidator.MAJOR_VERSION_WARNING, gradle_path, '9')

    @parameterized.expand([
        '1.6.0',
        '1.7.0',
        '1.8.9'
    ])
    def test_does_not_emit_warning_when_jvm_mv_8_or_less(self, version):
        version_string = ('JVM:          %s' % version).encode()
        gradle_path = '/path/to/gradle'
        mock_log = Mock()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils, log=mock_log)
        self.assertTrue(validator.validate(gradle_path=gradle_path))
        self.assertEqual(validator.validated_binary_path, gradle_path)
        mock_log.warning.assert_not_called()

    def test_gradle_executable_fails(self):
        version_string = 'java version "1.8.0"'.encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string, returncode=1)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils)
        with self.assertRaises(GradleBinaryValidatorError) as raised:
            validator.validate(gradle_path='/path/to/gradle')
        self.assertEqual(raised.exception.args[0], GradleBinaryValidatorError.MESSAGE)
