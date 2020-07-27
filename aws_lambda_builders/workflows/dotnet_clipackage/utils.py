"""
Commonly used utilities
"""

import os
import platform
import shutil
import subprocess
import zipfile
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

    def which(self, executable, executable_search_paths=None):
        return which(executable, executable_search_paths=executable_search_paths)

    def expand_zip(self, zipfullpath, destination_dir):
        ziparchive = zipfile.ZipFile(zipfullpath, "r")
        ziparchive.extractall(destination_dir)
        ziparchive.close()
        os.remove(zipfullpath)

    @property
    def pipe(self):
        return subprocess.PIPE
