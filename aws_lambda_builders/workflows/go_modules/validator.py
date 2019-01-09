"""
Go Runtime Validation
"""

import logging
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError

LOG = logging.getLogger(__name__)


class GoRuntimeValidator(object):
    SUPPORTED_RUNTIMES = {
        "go1.x"
    }

    def __init__(self, runtime, runtime_path):
        self.language = "go"
        self.runtime = runtime
        self.runtime_path = runtime_path

    def has_runtime(self):
        """
        Checks if the runtime is supported.
        :param string runtime: Runtime to check
        :return bool: True, if the runtime is supported.
        """
        return self.runtime in self.SUPPORTED_RUNTIMES

    def validate_runtime(self):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string runtime_path: runtime to check eg: /usr/bin/go
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        if not self.has_runtime():
            LOG.warning("'%s' runtime is not "
                        "a supported runtime", self.runtime_path)
            return

        expected_major_version = self.runtime.replace(self.language, "").split('.')[0]

        p = subprocess.Popen([self.runtime_path, "version"],
                             cwd=os.getcwd(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = p.communicate()

        mismatched = p.returncode != 0 \
            or len(out.split()) < 3 \
            or out.split()[2].replace(self.language, "").split('.')[0] != expected_major_version
        if mismatched:
            raise MisMatchRuntimeError(language=self.language,
                                       found_runtime=self.runtime_path,
                                       required_runtime=self.runtime,
                                       runtime_path=self.runtime_path)
