"""
Commonly used utilities
"""

import os
import platform
import tarfile
import subprocess
import shutil


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def copy_file(self, file_path, destination_path):
        return shutil.copy2(file_path, destination_path)

    def dir_exists(self, directory):
        return os.path.isdir(directory)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:
            tar.extractall(unpack_dir)

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def filename(self, filepath):
        return os.path.basename(filepath)

    def joinpath(self, *args):
        return os.path.join(*args)

    def mkdir(self, path, mode=0o777, *args, dir_fd=None):
        return os.mkdir(path, mode, *args, dir_fd=dir_fd)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    @property
    def pipe(self):
        return subprocess.PIPE

    def dirname(self, path):
        return os.path.dirname(path)

    def relative_path(self, path, start):
        return os.path.relpath(path, start=start)

    def remove_file(self, filename):
        return os.remove(filename)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return platform.system().lower() == "windows"
