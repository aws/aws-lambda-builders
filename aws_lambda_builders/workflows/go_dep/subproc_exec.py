"""
Wrapper around calling dep through a subprocess.
"""

import logging

LOG = logging.getLogger(__name__)


class ExecutionError(Exception):
    """
    Exception raised in case binary execution fails.
    It will pass on the standard error output from the binary console.
    """

    MESSAGE = "Exec Failed: {}"

    def __init__(self, message):
        raw_message = message
        if isinstance(message, bytes):
            message = message.decode("utf-8")

        try:
            Exception.__init__(self, self.MESSAGE.format(message.strip()))
        except UnicodeError:
            Exception.__init__(self, self.MESSAGE.format(raw_message.strip()))


class SubprocessExec(object):

    """
    Wrapper around the Dep command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, binary=None):
        """
        :type osutils: aws_lambda_builders.workflows.go_dep.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type binary: str
        :param binary: Path to the binary. If not set,
            the default executable path will be used
        """
        self.osutils = osutils

        self.binary = binary

    def run(self, args, cwd=None, env=None):

        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to the binary

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.go_dep.dep.ExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_bin = [self.binary] + args

        LOG.debug("executing binary: %s", invoke_bin)

        p = self.osutils.popen(invoke_bin, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd, env=env)

        out, err = p.communicate()

        if p.returncode != 0:
            raise ExecutionError(message=err)

        out = out.decode("utf-8") if isinstance(out, bytes) else out

        return out.strip()
