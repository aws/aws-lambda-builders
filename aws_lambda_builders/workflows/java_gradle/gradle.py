"""
Wrapper around calls to Gradle through a subprocess.
"""

import logging
import subprocess

LOG = logging.getLogger(__name__)


class GradleExecutionError(Exception):
    MESSAGE = "Gradle Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessGradle(object):

    def __init__(self, gradle_exec, os_utils=None):
        if gradle_exec is None:
            raise ValueError("Must provide path to a Gradle executable")
        self.gradle_exec = gradle_exec
        if os_utils is None:
            raise ValueError("Must provide OSUtils")
        self.os_utils = os_utils

    def build(self, source_dir, init_script_path=None):
        args = ['build']
        if init_script_path is not None:
            args += ['--init-script', init_script_path]
        ret_code, _, stderr = self._run(args, source_dir)
        if ret_code != 0:
            raise GradleExecutionError(message=stderr.decode('utf8').strip())

    def _run(self, args, cwd=None):
        p = self.os_utils.popen([self.gradle_exec] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr
