import os
from aws_lambda_builders.path_resolver import PathResolver
from .utils import OSUtils

class BundlerResolver(object):
    def __init__(self, source_dir, os_utils, path_resolver=None):
        self.source_dir = source_dir
        self.os_utils = OSUtils() if not os_utils else os_utils
        if os_utils.is_windows():
            self.binary = 'bundler.bat'
        else:
            self.binary = 'bundler'
        self.executables = [self.binary]
        self.path_resolver = PathResolver(binary=self.binary, runtime=None) if not path_resolver else path_resolver

    @property
    def exec_paths(self):
        return self.path_resolver.exec_paths
