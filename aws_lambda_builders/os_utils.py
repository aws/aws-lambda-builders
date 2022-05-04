"""
OSUtils implementation which is used in various workflows
"""
import json
import os
import platform
import shutil
import subprocess
import tarfile
import zipfile

from aws_lambda_builders.utils import which, copytree


class OSUtils:
    @property
    def pipe(self):
        return subprocess.PIPE

    @property
    def environ(self):
        return os.environ.copy()

    def joinpath(self, *args):
        return os.path.join(*args)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

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

    def exists(self, p):
        return os.path.exists(p)

    def makedirs(self, path):
        return os.makedirs(path)

    def normpath(self, path):
        return os.path.normpath(path)

    def which(self, executable, executable_search_paths=None):
        return which(executable, executable_search_paths=executable_search_paths)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:
            tar.extractall(unpack_dir)

    def copy_file(self, file_path, destination_path):
        return shutil.copy2(file_path, destination_path)

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def remove_file(self, filename):
        return os.remove(filename)

    def parse_json(self, path):
        with open(path) as json_file:
            return json.load(json_file)

    def expand_zip(self, zipfullpath, destination_dir):
        ziparchive = zipfile.ZipFile(zipfullpath, "r")
        ziparchive.extractall(destination_dir)
        ziparchive.close()
        os.remove(zipfullpath)

    def copy(self, src, dst):
        shutil.copy2(src, dst)
        return dst

    def move(self, src, dst):
        shutil.move(src, dst)

    def listdir(self, d):
        return os.listdir(d)

    def copytree(self, source, destination, ignore=None, include=None):
        copytree(source, destination, ignore=ignore, include=include)

    def rmtree(self, d):
        shutil.rmtree(d)
