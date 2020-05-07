"""
Commonly used utilities
"""

import os
import platform
import subprocess

from aws_lambda_builders.utils import which


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def exists(self, p):
        return os.path.exists(p)

    def makedirs(self, path):
        return os.makedirs(path)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    def environ(self):
        return os.environ.copy()

    def normpath(self, path):
        return os.path.normpath(path)

    def abspath(self, path):
        return os.path.abspath(path)

    @property
    def pipe(self):
        return subprocess.PIPE

    def is_windows(self):
        return platform.system().lower() == "windows"

    def which(self, executable, executable_search_paths=None):
        return which(executable, executable_search_paths=executable_search_paths)
