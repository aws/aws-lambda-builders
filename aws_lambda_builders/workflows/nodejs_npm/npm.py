"""
Wrapper around calling npm through a subprocess.
"""

import logging

LOG = logging.getLogger(__name__)


class NpmExecutionError(Exception):

    """
    Exception raised in case NPM execution fails.
    It will pass on the standard error output from the NPM console.
    """

    MESSAGE = "NPM Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessNpm(object):

    """
    Wrapper around the NPM command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, npm_exe=None):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type npm_exe: str
        :param npm_exe: Path to the NPM binary. If not set,
            the default executable path npm will be used
        """
        self.osutils = osutils

        if npm_exe is None:
            if osutils.is_windows():
                npm_exe = "npm.cmd"
            else:
                npm_exe = "npm"

        self.npm_exe = npm_exe

    def run(self, args, cwd=None):

        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to NPM

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.nodejs_npm.npm.NpmExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_npm = [self.npm_exe] + args

        LOG.debug("executing NPM: %s", invoke_npm)

        p = self.osutils.popen(invoke_npm, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise NpmExecutionError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()
