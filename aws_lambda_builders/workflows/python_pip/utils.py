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
import sys
import subprocess


class OSUtils(object):
    ZIP_DEFLATED = zipfile.ZIP_DEFLATED

    def environ(self):
        return os.environ

    def open(self, filename, mode):
        return open(filename, mode)

    def open_zip(self, filename, mode, compression=ZIP_DEFLATED):
        return zipfile.ZipFile(filename, mode, compression=compression)

    def remove_file(self, filename):
        """Remove a file, noop if file does not exist."""
        # Unlike os.remove, if the file does not exist,
        # then this method does nothing.
        try:
            os.remove(filename)
        except OSError:
            pass

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def get_file_contents(self, filename, binary=True, encoding='utf-8'):
        # It looks like the type definition for io.open is wrong.
        # the encoding arg is unicode, but the actual type is
        # Optional[Text].  For now we have to use Any to keep mypy happy.
        if binary:
            mode = 'rb'
            # In binary mode the encoding is not used and most be None.
            encoding = None
        else:
            mode = 'r'
        with io.open(filename, mode, encoding=encoding) as f:
            return f.read()

    def set_file_contents(self, filename, contents, binary=True):
        if binary:
            mode = 'wb'
        else:
            mode = 'w'
        with open(filename, mode) as f:
            f.write(contents)

    def extract_zipfile(self, zipfile_path, unpack_dir):
        with zipfile.ZipFile(zipfile_path, 'r') as z:
            z.extractall(unpack_dir)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, 'r:*') as tar:
            tar.extractall(unpack_dir)

    def directory_exists(self, path):
        return os.path.isdir(path)

    def get_directory_contents(self, path):
        return os.listdir(path)

    def makedirs(self, path):
        os.makedirs(path)

    def dirname(self, path):
        return os.path.dirname(path)

    def abspath(self, path):
        return os.path.abspath(path)

    def joinpath(self, *args):
        return os.path.join(*args)

    def walk(self, path):
        return os.walk(path)

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

    def copy(self, source, destination):
        shutil.copy(source, destination)

    def move(self, source, destination):
        shutil.move(source, destination)

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


class UI(object):
    def __init__(self, out=None, err=None):
        if out is None:
            out = sys.stdout
        if err is None:
            err = sys.stderr
        self._out = out
        self._err = err

    def write(self, msg):
        self._out.write(msg)

    def error(self, msg):
        self._err.write(msg)
