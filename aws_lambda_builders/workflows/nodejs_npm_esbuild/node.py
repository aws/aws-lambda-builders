"""
Wrapper around calling nodejs through a subprocess.
"""

import logging

from aws_lambda_builders.exceptions import LambdaBuilderError

LOG = logging.getLogger(__name__)


class NodejsExecutionError(LambdaBuilderError):

    """
    Exception raised in case nodejs execution fails.
    It will pass on the standard error output from the Node.js console.
    """

    MESSAGE = "Nodejs Failed: {message}"


class SubprocessNodejs(object):

    """
    Wrapper around the nodejs command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, executable_search_paths, which):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type executable_search_paths: list
        :param executable_search_paths: List of paths to the node package binary utilities. This will
            be used to find embedded Nodejs at runtime if present in the package

        :type which: aws_lambda_builders.utils.which
        :param which: Function to get paths which conform to the given mode on the PATH
            with the prepended additional search paths
        """
        self.osutils = osutils
        self.executable_search_paths = executable_search_paths
        self.which = which

    def nodejs_binary(self):
        """
        Finds the Nodejs binary at runtime.

        The utility may be present as a package dependency of the Lambda project,
        or in the global path. If there is one in the Lambda project, it should
        be preferred over a global utility. The check has to be executed
        at runtime, since nodejs dependencies will be installed by the workflow
        using one of the previous actions.
        """

        LOG.debug("checking for nodejs in: %s", self.executable_search_paths)
        binaries = self.which("node", executable_search_paths=self.executable_search_paths)
        LOG.debug("potential nodejs binaries: %s", binaries)

        if binaries:
            return binaries[0]
        else:
            raise NodejsExecutionError(message="cannot find nodejs")

    def run(self, args, cwd=None):

        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to Nodejs

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.nodejs_npm.npm.NodejsExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_nodejs = [self.nodejs_binary()] + args

        LOG.debug("executing Nodejs: %s", invoke_nodejs)

        p = self.osutils.popen(invoke_nodejs, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise NodejsExecutionError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()
