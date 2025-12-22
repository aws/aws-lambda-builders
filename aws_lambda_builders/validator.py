"""
No-op validator that does not validate the runtime_path for a specified language.
"""

import logging

from aws_lambda_builders.exceptions import UnsupportedArchitectureError, UnsupportedRuntimeError
from aws_lambda_builders.supported_runtimes import RUNTIME_ARCHITECTURES as SUPPORTED_RUNTIMES

LOG = logging.getLogger(__name__)


class RuntimeValidator(object):
    def __init__(self, runtime, architecture):
        """

        Parameters
        ----------
        runtime : str
            name of the AWS Lambda runtime that you are building for. This is sent to the builder for
            informational purposes.
        architecture : str
            Architecture for which the build will be based on in AWS lambda
        """
        self.runtime = runtime
        self._runtime_path = None
        self.architecture = architecture

    def validate(self, runtime_path):
        """
        Parameters
        ----------
        runtime_path : str
            runtime to check eg: /usr/bin/runtime

        Returns
        -------
        str
            runtime to check eg: /usr/bin/runtime

        Raises
        ------
        UnsupportedRuntimeError
            Raised when runtime provided is not support.

        UnsupportedArchitectureError
            Raised when runtime is not compatible with architecture
        """
        runtime_architectures = SUPPORTED_RUNTIMES.get(self.runtime, None)

        if not runtime_architectures:
            raise UnsupportedRuntimeError(runtime=self.runtime)
        if self.architecture not in runtime_architectures:
            raise UnsupportedArchitectureError(runtime=self.runtime, architecture=self.architecture)

        self._runtime_path = runtime_path
        return runtime_path
