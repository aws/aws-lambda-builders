"""
Commonly used utilities
"""

import os
import platform
import tarfile
import subprocess


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory

    TODO: move to somewhere generic
    """

    def joinpath(self, *args):
        return os.path.join(*args)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    @property
    def pipe(self):
        return subprocess.PIPE

    @property
    def environ(self):
        return os.environ.copy()

    def dirname(self, path):
        return os.path.dirname(path)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return platform.system().lower() == "windows"
