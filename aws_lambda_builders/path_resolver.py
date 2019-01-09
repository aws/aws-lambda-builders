"""
Basic Path Resolver that looks for the executable by runtime first, before proceeding to 'language' in PATH.
"""

from aws_lambda_builders.utils import which


class PathResolver(object):

    def __init__(self, binary, runtime):
        self.binary = binary
        self.runtime = runtime
        self.executables = [self.runtime, self.binary]

    def _which(self):
        exec_paths = []
        for executable in [executable for executable in self.executables if executable is not None]:
            paths = which(executable)
            exec_paths.extend(paths)

        if not exec_paths:
            raise ValueError("Path resolution for runtime: {} of binary: "
                             "{} was not successful".format(self.runtime, self.binary))
        return exec_paths

    @property
    def exec_paths(self):
        return self._which()
