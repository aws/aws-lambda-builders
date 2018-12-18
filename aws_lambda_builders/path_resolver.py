"""
Basic Path Resolver that just looks for the language in the path.
"""

from whichcraft import which


class PathResolver(object):

    def __init__(self, runtime):
        self.runtime = runtime

    @property
    def path(self):
        return which(self.runtime)
