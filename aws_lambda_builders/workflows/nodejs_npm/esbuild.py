"""
Wrapper around calling esbuild through a subprocess.
"""

import logging

LOG = logging.getLogger(__name__)


class EsbuildExecutionError(Exception):

    """
    Exception raised in case NPM execution fails.
    It will pass on the standard error output from the NPM console.
    """

    MESSAGE = "Esbuild Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessEsbuild(object):

    """
    Wrapper around the Esbuild command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, esbuild_exe=None):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type esbuild_exe: str
        :param esbuild_exe: Path to the Esbuild binary. If not set,
            the default executable path esbuild will be used
        """
        self.osutils = osutils

        if esbuild_exe is None:
            if osutils.is_windows():
                esbuild_exe = "esbuild.cmd"
            else:
                esbuild_exe = "esbuild"

        self.esbuild_exe = esbuild_exe

    def run(self, args, cwd=None):

        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to Esbuild

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.nodejs_npm.npm.EsbuildExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_esbuild = [self.esbuild_exe] + args

        LOG.debug("executing Esbuild: %s", invoke_esbuild)

        p = self.osutils.popen(invoke_esbuild, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise EsbuildExecutionError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()
