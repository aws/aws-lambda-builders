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

    def __init__(self, runtime):
        self.language = "go"
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
        :param string runtime_path: runtime to check eg: /usr/bin/go
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        if not self.has_runtime():
            LOG.warning("'%s' runtime is not "
                        "a supported runtime", self.runtime)
            return None

        expected_major_version = self.runtime.replace(self.language, "").split('.')[0]

        p = subprocess.Popen([runtime_path, "version"],
                             cwd=os.getcwd(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = p.communicate()

        mismatched = p.returncode != 0 \
            or len(out.split()) < 3 \
            or out.split()[2].decode().replace(self.language, "").split('.')[0] != expected_major_version
        if mismatched:
            raise MisMatchRuntimeError(language=self.language,
                                       required_runtime=self.runtime,
                                       runtime_path=runtime_path)
        else:
            self._valid_runtime_path = runtime_path
            return self._valid_runtime_path

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path if self._valid_runtime_path is not None else None
