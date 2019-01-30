"""
Commonly used utilities
"""

import os
import platform
import shutil
import subprocess


class OSUtils(object):
    """
    Convenience wrapper around common system functions
    """

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    def is_windows(self):
        return platform.system().lower() == 'windows'

    def copy(self, src, dst):
        shutil.copy2(src, dst)
        return dst

    def listdir(self, d):
        return os.listdir(d)

    def exists(selfself, p):
        return os.path.exists(p)

    @property
    def pipe(self):
        return subprocess.PIPE
