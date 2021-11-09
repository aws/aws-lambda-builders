"""
Maven Binary Validation
"""

import logging
import re

from aws_lambda_builders.workflows.java.utils import OSUtils
from aws_lambda_builders.validator import RuntimeValidator

LOG = logging.getLogger(__name__)


class MavenValidator(RuntimeValidator):
    VERSION_STRING_WARNING = (
        "%s failed to return a version string using the '-v' option. The workflow is unable to "
        "check that the version of the JVM used is compatible with AWS Lambda."
    )

    MAJOR_VERSION_WARNING = (
        "%s is using a JVM with major version %s which is newer than %s that is supported by AWS "
        "Lambda. The compiled function code may not run in AWS Lambda unless the project has "
        "been configured to be compatible with Java %s using 'maven.compiler.target' in Maven."
    )

    def __init__(self, runtime, architecture, os_utils=None, log=None):
        super(MavenValidator, self).__init__(runtime, architecture)
        self.language = "java"
        self._valid_binary_path = None
        self.os_utils = OSUtils() if not os_utils else os_utils
        self.log = LOG if not log else log

    def validate(self, runtime_path):
        """
        Parameters
        ----------
        runtime_path : str
            maven_path to check eg: /usr/bin/java8

        Returns
        -------
        str
           runtime to check for the java binaries eg: /usr/bin/java8
        """

        maven_path = super(MavenValidator, self).validate(runtime_path)
        jvm_mv = self._get_major_version(maven_path)

        language_version = self.runtime.replace("java", "")

        if jvm_mv:
            if int(jvm_mv) > int(language_version):
                self.log.warning(self.MAJOR_VERSION_WARNING, maven_path, jvm_mv, language_version, language_version)
        else:
            self.log.warning(self.VERSION_STRING_WARNING, maven_path)

        self._valid_binary_path = maven_path
        return self._valid_binary_path

    @property
    def validated_binary_path(self):
        return self._valid_binary_path

    def _get_major_version(self, maven_path):
        vs = self._get_jvm_string(maven_path)
        if vs:
            m = re.search(r"Java version:\s+([\d\.]+)", vs)
            version = m.group(1).split(".")
            # For Java 8 or earlier, version strings begin with 1.{Major Version}
            if version[0] == "1":
                return version[1]
            # Starting with Java 9, the major version is first
            return version[0]

    def _get_jvm_string(self, maven_path):
        p = self.os_utils.popen([maven_path, "-version"], stdout=self.os_utils.pipe, stderr=self.os_utils.pipe)
        stdout, _ = p.communicate()

        if p.returncode != 0:
            return None

        for l in stdout.splitlines():
            l_dec = l.decode()
            if l_dec.startswith("Java version"):
                return l_dec
