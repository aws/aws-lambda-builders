"""
Basic Path Resolver that just returns the runtime.
"""


class PathResolver(object):

    def __init__(self, runtime):
        self.runtime = runtime

    @property
    def path(self):
        return self.runtime
