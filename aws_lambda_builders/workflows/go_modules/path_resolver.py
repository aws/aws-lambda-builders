"""
Go Path Resolver that looks for the executable by runtime first, before proceeding to 'go' in PATH.
"""
import whichcraft


class GoPathResolver(object):

    def __init__(self, runtime, which=None):
        self.language = "go"
        self.runtime = runtime
        self.executables = [self.language]
        self.which = which or whichcraft.which

    def _which(self):
        for executable in self.executables:
            path = self.which(executable)
            if path:
                return path
        raise ValueError("Path resolution for runtime: {} of language: "
                         "{} was not successful".format(self.runtime, self.language))

    @property
    def exec_path(self):
        return self._which()
