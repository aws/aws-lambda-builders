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

    def __init__(self, binary_path, os_utils=None):
        if binary_path is None:
            raise ValueError("Must provide Gradle BinaryPath")
        self.binary_path = binary_path
        if os_utils is None:
            raise ValueError("Must provide OSUtils")
        self.os_utils = os_utils

    def build(self, source_dir, cache_dir=None, init_script_path=None, properties=None):
        args = ['build']
        if cache_dir is not None:
            args.extend(['--project-cache-dir', cache_dir])
        if properties is not None:
            args.extend(['-D%s=%s' % (n, v) for n, v in properties.items()])
        if init_script_path is not None:
            args.extend(['--init-script', init_script_path])
        ret_code, _, stderr = self._run(args, source_dir)
        if ret_code != 0:
            raise GradleExecutionError(message=stderr.decode('utf8').strip())

    def _run(self, args, cwd=None):
        p = self.os_utils.popen([self.binary_path.binary_path] + args, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr
