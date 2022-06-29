"""
Commonly used utilities
"""

import os
import platform
import tarfile
import subprocess
import shutil
import json


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def copy_file(self, file_path, destination_path):
        return shutil.copy2(file_path, destination_path)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:
            tar.extractall(unpack_dir)

    def file_exists(self, filename):
        return os.path.isfile(filename)

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

    def remove_file(self, filename):
        return os.remove(filename)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return platform.system().lower() == "windows"

    def parse_json(self, path):
        with open(path) as json_file:
            return json.load(json_file)

    def check_output(self, path):
        return subprocess.check_output(["node", path])
