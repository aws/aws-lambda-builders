"""
Wrapper around calling npm through a subprocess.
"""

import logging

LOG = logging.getLogger(__name__)


class NpmExecutionError(Exception):
    MESSAGE = "NPM Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessNpm(object):

    def __init__(self, osutils, npm_exe=None):
        self.osutils = osutils

        if npm_exe is None:
            npm_exe = 'npm'

        self.npm_exe = npm_exe

    def run(self, args, cwd=None):

        if not isinstance(args, list):
            raise ValueError('args must be a list')

        if not args:
            raise ValueError('requires at least one arg')

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
