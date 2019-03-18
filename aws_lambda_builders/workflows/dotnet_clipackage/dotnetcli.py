"""
Wrapper around calls to dotent CLI through a subprocess.
"""

import sys
import logging

from .utils import OSUtils

LOG = logging.getLogger(__name__)

class DotnetCLIExecutionError(Exception):
    """
    Exception raised when dotnet CLI fails.
    Will encapsulate error output from the command.
    """

    MESSAGE = "Dotnet CLI Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))

class SubprocessDotnetCLI(object):
    """
    Wrapper around the Dotnet CLI, encapsulating
    execution results.
    """

    def __init__(self, dotnet_exe=None, os_utils=None):
        self.os_utils = os_utils if os_utils else OSUtils()
        if dotnet_exe is None:
            if self.os_utils.is_windows():
                dotnet_exe = 'dotnet.exe'
            else:
                dotnet_exe = 'dotnet'

        self.dotnet_exe = dotnet_exe

    def run(self, args, cwd=None):
        if not isinstance(args, list):
            raise ValueError('args must be a list')

        if not args:
            raise ValueError('requires at least one arg')

        invoke_dotnet = [self.dotnet_exe] + args

        LOG.debug("executing dotnet: %s", invoke_dotnet)

        p = self.os_utils.popen(invoke_dotnet,
                             stdout=self.os_utils.pipe,
                             stderr=self.os_utils.pipe,
                             cwd=cwd)

        out, err = p.communicate()

        # The package command contains lots of useful information on how the package was created and
        # information when the package command was not successful. For that reason the output is
        # always written to the output to help developers diagnose issues.
        LOG.info(out.decode('utf8').strip())

        if p.returncode != 0:
            raise DotnetCLIExecutionError(message=err.decode('utf8').strip())
