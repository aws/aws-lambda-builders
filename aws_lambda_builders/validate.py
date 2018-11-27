"""
Supported Runtimes and their validations.
"""

import logging
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError

LOG = logging.getLogger(__name__)


def validate_python_cmd(required_language, required_runtime_version):
    major, minor = required_runtime_version.replace(required_language, "").split('.')
    cmd = [
        "python",
        "-c",
        "import sys; "
        "assert sys.version_info.major == {major} "
        "and sys.version_info.minor == {minor}".format(
            major=major,
            minor=minor)]
    return cmd


_RUNTIME_VERSION_RESOLVER = {
    "python": validate_python_cmd
}


class RuntimeValidator(object):
    SUPPORTED_RUNTIMES = [
        "python2.7",
        "python3.6"
    ]

    @classmethod
    def has_runtime(cls, runtime):
        """
        Checks if the runtime is supported.
        :param string runtime: Runtime to check
        :return bool: True, if the runtime is supported.
        """
        return runtime in cls.SUPPORTED_RUNTIMES

    @classmethod
    def validate_runtime(cls, required_language, required_runtime):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string required_language: language to check eg: python
        :param string required_runtime: runtime to check eg: python3.6
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        if required_language in _RUNTIME_VERSION_RESOLVER:
            if not RuntimeValidator.has_runtime(required_runtime):
                LOG.warning("'%s' runtime is not "
                            "a supported runtime", required_runtime)
                return
            cmd = _RUNTIME_VERSION_RESOLVER[required_language](required_language, required_runtime)

            p = subprocess.Popen(cmd,
                                 cwd=os.getcwd(),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.communicate()
            if p.returncode != 0:
                raise MisMatchRuntimeError(language=required_language,
                                           required_runtime=required_runtime)
        else:
            LOG.warning("'%s' runtime has not "
                        "been validated!", required_language)
