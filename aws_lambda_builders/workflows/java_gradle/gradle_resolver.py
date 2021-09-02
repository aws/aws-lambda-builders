"""
Gradle executable resolution
"""

from aws_lambda_builders.workflows.java.utils import OSUtils


class GradleResolver(object):
    def __init__(self, executable_search_paths=None, os_utils=None):
        self.binary = "gradle"
        self.executables = [self.binary]
        self.executable_search_paths = executable_search_paths
        self.os_utils = os_utils if os_utils else OSUtils()

    @property
    def exec_paths(self):
        # Prefer gradlew/gradlew.bat
        paths = self.os_utils.which(self.wrapper_name, executable_search_paths=self.executable_search_paths)
        if not paths:
            # fallback to the gradle binary
            paths = self.os_utils.which("gradle", executable_search_paths=self.executable_search_paths)

        if not paths:
            raise ValueError("No Gradle executable found!")

        return paths

    @property
    def wrapper_name(self):
        return "gradlew.bat" if self.os_utils.is_windows() else "gradlew"
