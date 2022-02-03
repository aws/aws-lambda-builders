"""
Commonly used utilities
"""

import io
import os
import zipfile
import contextlib
import tempfile
import shutil
import tarfile
import subprocess
import sys


class OSUtils(object):
    def environ(self):
        return os.environ

    def original_environ(self):
        # https://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
        env = dict(os.environ)
        # Check whether running as a PyInstaller binary
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            lp_key = "LD_LIBRARY_PATH"
            original_lp = env.get(lp_key + "_ORIG")
            if original_lp is not None:
                env[lp_key] = original_lp
            else:
                # This happens when LD_LIBRARY_PATH was not set.
                # Remove the env var as a last resort:
                env.pop(lp_key, None)

        return env

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def get_file_contents(self, filename, binary=True, encoding="utf-8"):
        # It looks like the type definition for io.open is wrong.
        # the encoding arg is unicode, but the actual type is
        # Optional[Text].  For now we have to use Any to keep mypy happy.
        if binary:
            mode = "rb"
            # In binary mode the encoding is not used and most be None.
            encoding = None
        else:
            mode = "r"
        with io.open(filename, mode, encoding=encoding) as f:
            return f.read()

    def extract_zipfile(self, zipfile_path, unpack_dir):
        with zipfile.ZipFile(zipfile_path, "r") as z:
            z.extractall(unpack_dir)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:
            tar.extractall(unpack_dir)

    def directory_exists(self, path):
        return os.path.isdir(path)

    def get_directory_contents(self, path):
        return os.listdir(path)

    def makedirs(self, path):
        os.makedirs(path)

    def joinpath(self, *args):
        return os.path.join(*args)

    def copytree(self, source, destination):
        if not os.path.exists(destination):
            self.makedirs(destination)
        names = self.get_directory_contents(source)
        for name in names:
            new_source = os.path.join(source, name)
            new_destination = os.path.join(destination, name)
            if os.path.isdir(new_source):
                self.copytree(new_source, new_destination)
            else:
                shutil.copy2(new_source, new_destination)

    def rmtree(self, directory):
        shutil.rmtree(directory)

    @contextlib.contextmanager
    def tempdir(self):
        tempdir = tempfile.mkdtemp()
        try:
            yield tempdir
        finally:
            shutil.rmtree(tempdir)

    def popen(self, command, stdout=None, stderr=None, env=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env)
        return p

    def mtime(self, path):
        return os.stat(path).st_mtime

    @property
    def pipe(self):
        return subprocess.PIPE

    def basename(self, path):
        # type: (str) -> str
        return os.path.basename(path)
