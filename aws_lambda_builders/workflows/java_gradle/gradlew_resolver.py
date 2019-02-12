"""
Gradle executable resolution
"""

from aws_lambda_builders.path_resolver import PathResolver


class GradlewResolver(object):
    DUMMY_PATH = object()

    def __init__(self, binary, executable_search_paths=None, path_resolver=None):
        self.binary = binary
        self.executables = [self.binary]
        if path_resolver is None:
            self.path_resolver = PathResolver(binary=self.binary, runtime=None,
                                              executable_search_paths=executable_search_paths)
        else:
            self.path_resolver = path_resolver

    @property
    def exec_paths(self):
        try:
            return self.path_resolver.exec_paths
        except ValueError as e:
            # gradlew is optional so we're okay with not finding the executable
            if str(e).startswith("Path resolution for runtime"):
                return [self.DUMMY_PATH]
            else:
                raise e
