"""
Dotnet executable resolution
"""

from aws_lambda_builders.utils import which


class DotnetCliResolver(object):

    def __init__(self, executable_search_paths=None, os_utils=None):
        self.binary = 'dotnet'
        self.executable_search_paths = executable_search_paths

    @property
    def exec_paths(self):

        # look for the windows executable
        paths = which('dotnet.exe', executable_search_paths=self.executable_search_paths)
        if not paths:
            # fallback to the non windows name without the .exe suffix
            paths = which('dotnet', executable_search_paths=self.executable_search_paths)

        if not paths:
            raise ValueError("No dotnet cli executable found!")

        return paths
