"""
Commonly used utilities
"""

import os
import platform
import shutil
import subprocess
from aws_lambda_builders.utils import which, copytree


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

    def copytree(self, source, destination, ignore=None, include=None):
        copytree(source, destination, ignore=ignore, include=include)

    def makedirs(self, d):
        return os.makedirs(d)

    def rmtree(self, d):
        shutil.rmtree(d)

    @property
    def pipe(self):
        return subprocess.PIPE


def jar_file_filter(file_name):
    """
    A function that will filter .jar files for copy operation

    :type file_name: str
    :param file_name:
        Name of the file that will be checked against if it ends with .jar or not
    """
    return bool(file_name) and isinstance(file_name, str) and file_name.endswith(".jar")
