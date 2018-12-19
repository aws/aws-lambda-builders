"""
Ruby Path Resolver that looks for the executable by runtime first, before proceeding to 'ruby' in PATH.
"""

from whichcraft import which


class RubyPathResolver(object):

    def __init__(self, runtime):
        self.language = 'ruby'
        self.runtime = runtime
        self.executables = [self.runtime, self.language]

    def _which(self):
        for executable in self.executables:
            path = which(executable)
            if path:
                return path
        raise ValueError("Path resolution for runtime: {} of language: "
                         "{} was not successful".format(self.runtime, self.language))

    @property
    def path(self):
        return self._which()
