from unittest import TestCase

from mock import patch, Mock
from parameterized import parameterized
from aws_lambda_builders.workflows.java_gradle.gradle_validator import GradleBinaryValidator
from aws_lambda_builders.workflows.java_gradle.gradlew_resolver import GradlewResolver


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
        self.mock_log = Mock()
        self.gradle_path = '/path/to/gradle'

    @parameterized.expand([
        '1.7.0',
        '1.8.9',
        '11.0.0'
    ])
    def test_accepts_any_jvm_mv(self, version):
        version_string = ('JVM:          %s' % version).encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils)
        self.assertTrue(validator.validate(gradle_path=self.gradle_path))
        self.assertEqual(validator.validated_binary_path, self.gradle_path)

    def test_emits_warning_when_jvm_mv_greater_than_8(self):
        version_string = 'JVM:          9.0.0'.encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils, log=self.mock_log)
        self.assertTrue(validator.validate(gradle_path=self.gradle_path))
        self.assertEqual(validator.validated_binary_path, self.gradle_path)
        self.mock_log.warning.assert_called_with(GradleBinaryValidator.MAJOR_VERSION_WARNING, self.gradle_path, '9')

    @parameterized.expand([
        '1.6.0',
        '1.7.0',
        '1.8.9'
    ])
    def test_does_not_emit_warning_when_jvm_mv_8_or_less(self, version):
        version_string = ('JVM:          %s' % version).encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils, log=self.mock_log)
        self.assertTrue(validator.validate(gradle_path=self.gradle_path))
        self.assertEqual(validator.validated_binary_path, self.gradle_path)
        self.mock_log.warning.assert_not_called()

    def test_emits_warning_when_gradle_excutable_fails(self):
        version_string = 'JVM:          9.0.0'.encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string, returncode=1)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils, log=self.mock_log)
        validator.validate(gradle_path=self.gradle_path)
        self.mock_log.warning.assert_called_with(GradleBinaryValidator.VERSION_STRING_WARNING, self.gradle_path)

    def test_emits_warning_when_version_string_not_found(self):
        version_string = 'The Java Version:          9.0.0'.encode()
        self.mock_os_utils.popen.side_effect = [FakePopen(stdout=version_string, returncode=0)]
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils, log=self.mock_log)
        validator.validate(gradle_path=self.gradle_path)
        self.mock_log.warning.assert_called_with(GradleBinaryValidator.VERSION_STRING_WARNING, self.gradle_path)

    def test_accepts_dummy_path_from_gradlew_resolver(self):
        validator = GradleBinaryValidator(os_utils=self.mock_os_utils)
        self.assertEquals(GradlewResolver.DUMMY_PATH, validator.validate(GradlewResolver.DUMMY_PATH))
