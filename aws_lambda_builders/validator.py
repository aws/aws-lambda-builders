"""
Base Class for Runtime Validators
"""

import abc
import six


@six.add_metaclass(abc.ABCMeta)
class RuntimeValidator(object):
    SUPPORTED_RUNTIMES = []

    @abc.abstractmethod
    def has_runtime(self):
        """
        Checks if the runtime is supported.
        :param string runtime: Runtime to check
        :return bool: True, if the runtime is supported.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def validate_runtime(self, runtime_path):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string runtime_path: runtime language path to validate
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        raise NotImplementedError
