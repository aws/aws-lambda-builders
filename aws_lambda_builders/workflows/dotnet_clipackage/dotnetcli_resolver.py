"""
Dotnet executable resolution
"""

from .utils import OSUtils


class DotnetCliResolver(object):
    def __init__(self, executable_search_paths=None, os_utils=None):
        self.binary = "dotnet"
        self.executable_search_paths = executable_search_paths
        self.os_utils = os_utils if os_utils else OSUtils()

    @property
    def exec_paths(self):

        # look for the windows executable
        paths = self.os_utils.which("dotnet.exe", executable_search_paths=self.executable_search_paths)
        if not paths:
            # fallback to the non windows name without the .exe suffix
            paths = self.os_utils.which("dotnet", executable_search_paths=self.executable_search_paths)

        if not paths:
            raise ValueError("No dotnet cli executable found!")

        return paths
