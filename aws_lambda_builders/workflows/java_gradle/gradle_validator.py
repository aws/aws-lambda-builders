"""
Gradle Binary Validation
"""

import logging
import re

from aws_lambda_builders.exceptions import LambdaBuilderError
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class GradleBinaryValidatorError(LambdaBuilderError):
    MESSAGE = "gradle executable found failed to return version"


class GradleBinaryValidator(object):
    MAJOR_VERSION_WARNING = "%s is using a JVM with major version %s which is newer than 8 that is supported by AWS " \
                            "Lambda. The compiled function code may not run in AWS Lambda unless the project has " \
                            "been configured to be compatible with Java 8 using 'targetCompatibility' in Gradle."

    def __init__(self, os_utils=None, log=None):
        self.language = 'java'
        self._valid_binary_path = None
        self.os_utils = OSUtils() if not os_utils else os_utils
        self.log = LOG if not log else log

    def validate(self, gradle_path):
        jvm_mv = self._get_major_version(gradle_path)

        if int(jvm_mv) > 8:
            self.log.warning(self.MAJOR_VERSION_WARNING, gradle_path, jvm_mv)

        self._valid_binary_path = gradle_path
        return self._valid_binary_path

    @property
    def validated_binary_path(self):
        return self._valid_binary_path

    def _get_major_version(self, gradle_path):
        vs = self._get_jvm_string(gradle_path)
        m = re.search(r'JVM:\s+(\d.*)', vs)
        version = m.group(1).split('.')
        # For Java 8 or earlier, version strings begin with 1.{Major Version}
        if version[0] == '1':
            return version[1]
        # Starting with Java 9, the major version is first
        return version[0]

    def _get_jvm_string(self, gradle_path):
        p = self.os_utils.popen([gradle_path, '-version'], stdout=self.os_utils.pipe, stderr=self.os_utils.pipe)
        stdout, _ = p.communicate()
        if p.returncode != 0:
            raise GradleBinaryValidatorError()
        for l in stdout.splitlines():
            l_dec = l.decode()
            if l_dec.startswith('JVM'):
                return l_dec
