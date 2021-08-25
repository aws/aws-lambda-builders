"""
Go Runtime Validation
"""

import logging
import re
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError

LOG = logging.getLogger(__name__)


class GoRuntimeValidator(object):
    LANGUAGE = "go"
    SUPPORTED_RUNTIMES = {"go1.x"}
    GO_VERSION_REGEX = re.compile("go(\\d)\\.(x|\\d+)")

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

    @staticmethod
    def get_go_versions(version_string):
        parts = GoRuntimeValidator.GO_VERSION_REGEX.findall(version_string)
        try:
            # NOTE(sriram-mv): The version parts need to be a list with a major and minor version.
            return int(parts[0][0]), int(parts[0][1])
        except IndexError:
            return 0, 0

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
        version_string, _ = p.communicate()

        if p.returncode == 0:
            major_version, minor_version = GoRuntimeValidator.get_go_versions(version_string.decode())
            if major_version == expected_major_version and minor_version >= min_expected_minor_version:
                self._valid_runtime_path = runtime_path
                return self._valid_runtime_path

        # otherwise, raise mismatch exception
        raise MisMatchRuntimeError(language=self.LANGUAGE, required_runtime=self.runtime, runtime_path=runtime_path)

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path
