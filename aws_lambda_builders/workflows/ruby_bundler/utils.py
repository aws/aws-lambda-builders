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

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:

            def is_within_directory(directory, target):

                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)

                prefix = os.path.commonprefix([abs_directory, abs_target])

                return prefix == abs_directory

            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):

                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")

                tar.extractall(path, members, numeric_owner=numeric_owner)

            safe_extract(tar, unpack_dir)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    def joinpath(self, *args):
        return os.path.join(*args)

    @property
    def pipe(self):
        return subprocess.PIPE

    def dirname(self, path):
        return os.path.dirname(path)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return platform.system().lower() == "windows"

    def directory_exists(self, dirpath):
        return os.path.exists(dirpath) and os.path.isdir(dirpath)

    def remove_directory(self, dirpath):
        shutil.rmtree(dirpath)

    def get_bundle_dir(self, cwd):
        return os.path.join(cwd, ".bundle")
