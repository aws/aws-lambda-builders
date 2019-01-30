"""
Gradle executable resolution
"""

import os
from aws_lambda_builders.path_resolver import PathResolver
from .utils import OSUtils


class GradleResolver(object):
    def __init__(self, source_dir, os_utils, path_resolver=None):
        self.source_dir = source_dir
        self.os_utils = OSUtils() if not os_utils else os_utils
        self.binary = 'gradle'
        self.executables = [self.binary]
        self.path_resolver = PathResolver(binary='gradle', runtime=None) if not path_resolver else path_resolver

    @property
    def exec_paths(self):
        if self._includes_gradlew():
            return [self._gradlew_path()]
        return self.path_resolver.exec_paths

    def _gradlew_path(self):
        gradlew_name = 'gradlew.bat' if self.os_utils.is_windows() else 'gradlew'
        return os.path.join(self.source_dir, gradlew_name)

    def _includes_gradlew(self):
        gradlew = self._gradlew_path()
        return self.os_utils.exists(gradlew)
