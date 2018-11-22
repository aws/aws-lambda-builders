"""
Supported Runtimes and their validations.
"""

import logging
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError
from aws_lambda_builders.validator import RuntimeValidator

LOG = logging.getLogger(__name__)


class PythonRuntimeValidator(RuntimeValidator):
    SUPPORTED_RUNTIMES = [
        "python2.7",
        "python3.6"
    ]

    def __init__(self, language_runtime):
        self.language = "python"
        self.language_runtime = language_runtime

    def has_runtime(self):
        """
        Checks if the runtime is supported.
        :param string runtime: Runtime to check
        :return bool: True, if the runtime is supported.
        """
        return self.language_runtime in self.SUPPORTED_RUNTIMES

    def validate_runtime(self, runtime_path):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string required_language: language to check eg: python
        :param string required_runtime: runtime to check eg: python3.6
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        if not self.has_runtime():
            LOG.warning("'%s' runtime is not "
                        "a supported runtime", self.language_runtime)
            return
        cmd = self._validate_python_cmd(runtime_path)

        p = subprocess.Popen(cmd,
                             cwd=os.getcwd(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        if p.returncode != 0:
            raise MisMatchRuntimeError(language=self.language,
                                       required_runtime=self.language_runtime)

    def _validate_python_cmd(self, runtime_path):
        major, minor = self.language_runtime.replace(self.language, "").split('.')
        cmd = [
            runtime_path,
            "-c",
            "import sys; "
            "assert sys.version_info.major == {major} "
            "and sys.version_info.minor == {minor}".format(
                major=major,
                minor=minor)]
        return cmd
