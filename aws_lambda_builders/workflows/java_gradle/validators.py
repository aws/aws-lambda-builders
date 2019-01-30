"""
Java Runtime Validation
"""

import logging
import re

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class JavaRuntimeValidator(object):
    SUPPORTED_RUNTIMES = {
        "java",
        "java8"
    }

    MAJOR_VERSION_WARNING = "'%s' has a major version %s which is newer than 8 that is supported AWS Lambda. " \
                            "The compiled function code may not run in AWS Lambda unless the project has been " \
                            "configured to be compatible with Java 8 using 'targetCompatibility' in Gradle."

    def __init__(self, runtime, os_utils=None, log=None):
        self.language = "java"
        self.runtime = runtime
        self.os_utils = OSUtils() if not os_utils else os_utils
        self.log = LOG if not log else log
        self._valid_runtime_path = None

    def has_runtime(self):
        """
        Checks if the runtime is supported.
        :param string runtime: Runtime to check
        :return bool: True, if the runtime is supported.
        """
        return self.runtime in self.SUPPORTED_RUNTIMES

    def validate(self, runtime_path):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string runtime_path: runtime to check eg: /usr/bin/python3.6
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        if not self.has_runtime():
            self.log.warning("'%s' runtime is not "
                             "a supported runtime", self.runtime)
            return

        runtime_mv = self._get_major_version(runtime_path)

        if int(runtime_mv) > 8:
            self.log.warning(self.MAJOR_VERSION_WARNING, runtime_path, runtime_mv)

        self._valid_runtime_path = runtime_path
        return self._valid_runtime_path

    def _get_major_version(self, runtime_path):
        vs = self._get_version_string(runtime_path)
        m = re.search('java version "(.*)"', vs)
        version = m.group(1).split('.')
        # For Java 8 or earlier, version strings begin with 1.{Major Version}
        if version[0] == '1':
            return version[1]
        # Starting with Java 9, the major version is first
        return version[0]

    def _get_version_string(self, runtime_path):
        p = self.os_utils.popen([runtime_path, '-version'], stdout=self.os_utils.pipe, stderr=self.os_utils.pipe)
        _, stderr = p.communicate()
        if p.returncode != 0:
            raise MisMatchRuntimeError(language=self.language,
                                       required_runtime=self.runtime,
                                       runtime_path=runtime_path)
        return str(stderr.splitlines()[0])

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path


class GradleBinaryValidator(object):
    def __init__(self):
        self._valid_runtime_path = None

    def validate(self, binary_path):
        # We just need Gradle to be available on the PATH for now
        self._valid_runtime_path = binary_path
        return self._valid_runtime_path

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path
