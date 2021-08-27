"""
Maven executable resolution
"""

from aws_lambda_builders.workflows.java.utils import OSUtils


class MavenResolver(object):
    def __init__(self, executable_search_paths=None, os_utils=None):
        self.binary = "mvn"
        self.executables = [self.binary]
        self.executable_search_paths = executable_search_paths
        self.os_utils = os_utils if os_utils else OSUtils()

    @property
    def exec_paths(self):
        paths = self.os_utils.which("mvn", executable_search_paths=self.executable_search_paths)

        if not paths:
            raise ValueError("No Maven executable found!")

        return paths
