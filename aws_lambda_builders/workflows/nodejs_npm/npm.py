"""
Wrapper around calling npm through a subprocess.
"""

import logging

from aws_lambda_builders.exceptions import LambdaBuilderError

from .utils import OSUtils

LOG = logging.getLogger(__name__)


class NpmExecutionError(LambdaBuilderError):
    MESSAGE = "NPM Failed: {message}"


class SubprocessNpm(object):

    def __init__(self, osutils=None, npm_exe=None):
        if osutils is None:
            osutils = OSUtils()
        self.osutils = osutils

        if npm_exe is None:
            npm_exe = 'npm'

        self.npm_exe = npm_exe

    def run(self, args, cwd=None):

        if not isinstance(args, list):
            raise ValueError('args must be a list')

        invoke_npm = [self.npm_exe] + args

        LOG.debug("executing NPM: %s", invoke_npm)

        p = self.osutils.popen(invoke_npm,
                               stdout=self.osutils.pipe,
                               stderr=self.osutils.pipe,
                               cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise NpmExecutionError(message=err.decode('utf8').strip())

        return out.decode('utf8').strip()
