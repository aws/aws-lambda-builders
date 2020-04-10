"""
Make executable resolution
"""

from .utils import OSUtils


class MakeResolver(object):
    def __init__(self, executable_search_paths=None, os_utils=None):
        self.binary = "make"
        self.executables = [self.binary]
        self.executable_search_paths = executable_search_paths
        self.os_utils = os_utils if os_utils else OSUtils()

    @property
    def exec_paths(self):
        paths = self.os_utils.which("make", executable_search_paths=self.executable_search_paths)

        if not paths:
            raise ValueError("No Make executable found!")

        return paths