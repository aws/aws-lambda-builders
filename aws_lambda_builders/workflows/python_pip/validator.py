"""
Python Runtime Validation
"""

import logging
import os
import subprocess

from aws_lambda_builders.validator import RuntimeValidator
from aws_lambda_builders.exceptions import MisMatchRuntimeError
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class PythonRuntimeValidator(RuntimeValidator):
    def __init__(self, runtime, architecture):
        super(PythonRuntimeValidator, self).__init__(runtime, architecture)
        self.language = "python"
        self._valid_runtime_path = None

    def validate(self, runtime_path):
        """
        Checks if the language supplied matches the required lambda runtime

        Parameters
        ----------
        runtime_path : str
            runtime to check eg: /usr/bin/go

        Returns
        -------
        str
            runtime_path, runtime to check eg: /usr/bin/python3.6

        Raises
        ------
        MisMatchRuntimeError
            Raise runtime is not support or runtime does not support architecture.
        """

        runtime_path = super(PythonRuntimeValidator, self).validate(runtime_path)

        cmd = self._validate_python_cmd(runtime_path)

        p = subprocess.Popen(
            cmd, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=OSUtils().original_environ()
        )
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
