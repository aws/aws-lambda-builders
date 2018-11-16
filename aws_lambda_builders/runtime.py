"""
Supported Runtimes and their validations.
"""

import os
import subprocess
from enum import Enum

from aws_lambda_builders.exceptions import MisMatchRuntimeError


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


class Runtime(Enum):
    python27 = "python2.7"
    python36 = "python3.6"

    @classmethod
    def has_value(cls, value):
        """
        Checks if the enum has this value
        :param string value: Value to check
        :return bool: True, if enum has the value
        """
        return any(value == item.value for item in cls)

    @classmethod
    def validate_runtime(cls, required_language, required_runtime):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string required_language: language to check eg: python
        :param string required_runtime: runtime to check eg: python3.6
        :raises ValueError: Unsupported Lambda Runtime
        :raises MisMatchRuntimeError: Version mismatch of the lanugage vs the required runtime
        """
        try:
            cmd = _RUNTIME_VERSION_RESOLVER[required_language](required_language, required_runtime)
        except KeyError:
            # The language is not currently supported, so there is no runtime validation.
            return
        if not Runtime.has_value(required_runtime):
            raise ValueError("Unsupported Lambda runtime {}".format(required_runtime))

        p = subprocess.Popen(cmd,
                             cwd=os.getcwd(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        if p.returncode != 0:
            raise MisMatchRuntimeError(language=required_language,
                                       required_runtime=required_runtime)
