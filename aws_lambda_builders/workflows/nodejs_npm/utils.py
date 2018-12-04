"""
Commonly used utilities
"""

import os
import tarfile
import subprocess
import sys


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, 'r:*') as tar:
            tar.extractall(unpack_dir)

    def joinpath(self, *args):
        return os.path.join(*args)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    @property
    def pipe(self):
        return subprocess.PIPE

    def dirname(self, path):
        return os.path.dirname(path)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return sys.platform.lower().startswith('win')
