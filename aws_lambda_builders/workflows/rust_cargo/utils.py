import os
import shutil
import subprocess


class OSUtils(object):
    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        return subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)

    def copyfile(self, source, destination):
        shutil.copy2(source, destination)

    def makedirs(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
