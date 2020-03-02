"""
Go Runtime Validation
"""

import logging
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError

LOG = logging.getLogger(__name__)


class GoRuntimeValidator(object):

    LANGUAGE = "go"
    SUPPORTED_RUNTIMES = {"go1.x"}

    def __init__(self, runtime):
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
            LOG.warning("'%s' runtime is not " "a supported runtime", self.runtime)
            return None

        expected_major_version = int(self.runtime.replace(self.LANGUAGE, "").split(".")[0])
        min_expected_minor_version = 11 if expected_major_version == 1 else 0

        p = subprocess.Popen([runtime_path, "version"], cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = p.communicate()

        if p.returncode == 0:
            out_parts = out.decode().split()
            if len(out_parts) >= 3:
                version_parts = [int(x.replace("rc", "")) for x in out_parts[2].replace(self.LANGUAGE, "").split(".")]
                if len(version_parts) >= 2:
                    if version_parts[0] == expected_major_version and version_parts[1] >= min_expected_minor_version:
                        self._valid_runtime_path = runtime_path
                        return self._valid_runtime_path

        # otherwise, raise mismatch exception
        raise MisMatchRuntimeError(language=self.LANGUAGE, required_runtime=self.runtime, runtime_path=runtime_path)

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path
