"""
Commonly used utilities
"""

import os
import platform
import shutil
import subprocess
from aws_lambda_builders.utils import which


class OSUtils(object):
    """
    Convenience wrapper around common system functions
    """

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    def is_windows(self):
        return platform.system().lower() == "windows"

    def copy(self, src, dst):
        shutil.copy2(src, dst)
        return dst

    def move(self, src, dst):
        shutil.move(src, dst)

    def listdir(self, d):
        return os.listdir(d)

    def exists(self, p):
        return os.path.exists(p)

    def which(self, executable, executable_search_paths=None):
        return which(executable, executable_search_paths=executable_search_paths)

    def copytree(self, source, destination):
        if not os.path.exists(destination):
            self.makedirs(destination)
        names = self.listdir(source)
        for name in names:
            new_source = os.path.join(source, name)
            new_destination = os.path.join(destination, name)
            if os.path.isdir(new_source):
                self.copytree(new_source, new_destination)
            else:
                self.copy(new_source, new_destination)

    def makedirs(self, d):
        return os.makedirs(d)

    def rmtree(self, d):
        shutil.rmtree(d)

    @property
    def pipe(self):
        return subprocess.PIPE
