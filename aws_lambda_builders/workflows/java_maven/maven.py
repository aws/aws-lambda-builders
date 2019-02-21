"""
Wrapper around calls to Maven through a subprocess.
"""

import logging
import subprocess

LOG = logging.getLogger(__name__)


class MavenExecutionError(Exception):
    MESSAGE = "Maven Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessMaven(object):

    def __init__(self, maven_binary, os_utils=None):
        if maven_binary is None:
            raise ValueError("Must provide Maven BinaryPath")
        self.maven_binary = maven_binary
        if os_utils is None:
            raise ValueError("Must provide OSUtils")
        self.os_utils = os_utils

    def build(self, source_dir, module_name=None, root_dir=None, properties=None):

        args = ['clean']
        if properties is not None:
            args.extend(['-D%s=%s' % (n, v) for n, v in properties.items()])
        if module_name is not None:
            args.extend(['install', '-pl', module_name, '--also-make'])
        else:
            args.extend(['package'])
        if root_dir is not None:
            source_dir = root_dir
        ret_code, _, stderr = self._run(args, source_dir)
        if ret_code != 0:
            raise MavenExecutionError(message=stderr.decode('utf8').strip())

    def copy_dependency(self, source_dir, module_name=None, root_dir=None):

        args = ['dependency:copy-dependencies']
        if module_name is not None:
            args.extend(['-pl', module_name, '--also-make'])
        if root_dir is not None:
            source_dir = root_dir
        ret_code, _, stderr = self._run(args, source_dir)
        if ret_code != 0:
            raise MavenExecutionError(message=stderr.decode('utf8').strip())

    def cleanup(self, source_dir, module_name=None, root_dir=None):
        args = ['clean']
        if module_name is not None:
            args.extend(['-pl', module_name, '--also-make'])
        if root_dir is not None:
            source_dir = root_dir
        ret_code, _, stderr = self._run(args, source_dir)
        if ret_code != 0:
            raise MavenExecutionError(message=stderr.decode('utf8').strip())

    def _run(self, args, cwd=None):
        p = self.os_utils.popen([self.maven_binary.binary_path] + args, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr
