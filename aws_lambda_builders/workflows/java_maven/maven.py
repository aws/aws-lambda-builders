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

    def retrieve_module_name(self, scratch_dir):
        args = ['-q', '-Dexec.executable=echo', '-Dexec.args=${project.artifactId}',
                'exec:exec', '--non-recursive']
        ret_code, stdout, stderr = self._run(args, scratch_dir)
        if ret_code != 0:
            raise MavenExecutionError(message=stderr.decode('utf8').strip())
        return stdout.decode('utf8').strip()

    def build(self, scratch_dir, module_name):
        args = ['clean', 'install', '-pl', ':' + module_name, '-am']
        ret_code, stdout, stderr = self._run(args, scratch_dir)

        LOG.debug("Maven logs: %s", stdout.decode('utf8').strip())

        if ret_code != 0:
            raise MavenExecutionError(message=stderr.decode('utf8').strip())

    def copy_dependency(self, scratch_dir, module_name):
        args = ['dependency:copy-dependencies', '-DincludeScope=compile', '-pl', ':' + module_name]
        ret_code, _, stderr = self._run(args, scratch_dir)
        if ret_code != 0:
            raise MavenExecutionError(message=stderr.decode('utf8').strip())

    def _run(self, args, cwd=None):
        p = self.os_utils.popen([self.maven_binary.binary_path] + args, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr
