"""
Wrapper around calls to dotent CLI through a subprocess.
"""

import platform
import subprocess
import logging

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

    def __init__(self, dotnet_exe=None):
        if dotnet_exe is None:
            if platform.system().lower() == 'windows':
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

        p = subprocess.Popen(invoke_dotnet,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             cwd=cwd)

        out, err = p.communicate()

        # The package command contains lots of useful information on how the package was created and
        # information when the package command was not successful. For that reason the output is
        # always written to the output to help developers diagnose issues.
        print(out.decode('utf8').strip())

        if p.returncode != 0:
            raise DotnetCLIExecutionError(message=err.decode('utf8').strip())
