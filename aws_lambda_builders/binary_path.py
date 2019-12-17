"""
Class containing resolved path of binary given a validator and a resolver and the name of the binary.
"""


class BinaryPath(object):
    def __init__(self, resolver, validator, binary, binary_path=None):
        self.resolver = resolver
        self.validator = validator
        self.binary = binary
        self._binary_path = binary_path
        self.path_provided = True if self._binary_path else False

    @property
    def binary_path(self):
        return self._binary_path

    @binary_path.setter
    def binary_path(self, binary_path):
        self._binary_path = binary_path
