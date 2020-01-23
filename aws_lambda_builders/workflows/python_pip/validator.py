"""
Python Runtime Validation
"""

import logging
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError

LOG = logging.getLogger(__name__)


class PythonRuntimeValidator(object):
    SUPPORTED_RUNTIMES = {"python2.7", "python3.6", "python3.7", "python3.8"}

    def __init__(self, runtime):
        self.language = "python"
        self.runtime = runtime
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
            LOG.warning("'%s' runtime is not " "a supported runtime", self.runtime)
            return

        cmd = self._validate_python_cmd(runtime_path)

        p = subprocess.Popen(cmd, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        if p.returncode != 0:
            raise MisMatchRuntimeError(language=self.language, required_runtime=self.runtime, runtime_path=runtime_path)
        else:
            self._valid_runtime_path = runtime_path
            return self._valid_runtime_path

    def _validate_python_cmd(self, runtime_path):
        major, minor = self.runtime.replace(self.language, "").split(".")
        cmd = [
            runtime_path,
            "-c",
            "import sys; "
            "assert sys.version_info.major == {major} "
            "and sys.version_info.minor == {minor}".format(major=major, minor=minor),
        ]
        return cmd

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path
