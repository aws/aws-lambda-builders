"""
Wrapper around calling npm through a subprocess.
"""

import logging

from aws_lambda_builders.workflows.python_pip.utils import OSUtils

LOG = logging.getLogger(__name__)


class NpmError(Exception):
    pass


class NpmExecutionError(NpmError):
    def __init__(self, err):
        super(NpmExecutionError, self).__init__(
            'NPM failed: %s' % err)


class SubprocessNpm(object):

    def __init__(self, osutils=None, npm_exe=None):
        if osutils is None:
            osutils = OSUtils()
        self.osutils = osutils

        if npm_exe is None:
            npm_exe = 'npm'

        self.npm_exe = npm_exe

    def main(self, args, cwd=None):

        if not isinstance(args, list):
            raise NpmExecutionError('args must be a list')

        invoke_npm = [self.npm_exe] + args

        LOG.debug("executing NPM: %s", invoke_npm)

        p = self.osutils.popen(invoke_npm,
                               stdout=self.osutils.pipe,
                               stderr=self.osutils.pipe,
                               cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise NpmExecutionError(err.decode('utf8').strip())

        return out.decode('utf8').strip()
