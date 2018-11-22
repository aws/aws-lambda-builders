from aws_lambda_builders.utils import which


class PathResolver(object):

    def __init__(self, language, runtime):
        self.language = language
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
