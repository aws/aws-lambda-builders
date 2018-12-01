"""
Wrapper around calling npm through a subprocess.
"""

import logging

from aws_lambda_builders.workflows.python_pip.utils import OSUtils

LOG = logging.getLogger(__name__)


class NpmError(Exception):
    pass


class NpmNotFoundError(NpmError):
    def __init__(self, npm_path):
        super(NpmNotFoundError, self).__init__(
            'NPM executable not found: %s' % npm_path)


class NpmExecutionError(NpmError):
    def __init__(self, err):
        super(NpmExecutionError, self).__init__(
            'NPM failed: %s' % err)


class SubprocessNpm(object):

    def __init__(self, osutils=None, npm_exe=None):
        if osutils is None:
            osutils = OSUtils()
        self._osutils = osutils

        if npm_exe is None:
            npm_exe = osutils.find_executable('npm')

        if not osutils.file_exists(npm_exe):
            raise NpmNotFoundError(npm_exe)

        self.npm_exe = npm_exe

    def main(self, args, cwd=None, env_vars=None):
        if env_vars is None:
            env_vars = self._osutils.environ()

        invoke_npm = [self.npm_exe] + args

        LOG.debug("executing NPM: %s", invoke_npm)

        p = self._osutils.popen(invoke_npm,
                                stdout=self._osutils.pipe,
                                stderr=self._osutils.pipe,
                                env=env_vars,
                                cwd=cwd)

        out, err = p.communicate()

        if (p.returncode != 0):
            raise NpmExecutionError(err.decode('utf8').strip())

        return out.decode('utf8').strip()
