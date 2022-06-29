"""
Wrapper around calling esbuild through a subprocess.
"""

import logging

from aws_lambda_builders.exceptions import LambdaBuilderError

LOG = logging.getLogger(__name__)


class EsbuildExecutionError(LambdaBuilderError):

    """
    Exception raised in case esbuild execution fails.
    It will pass on the standard error output from the esbuild console.
    """

    MESSAGE = "Esbuild Failed: {message}"


class SubprocessEsbuild(object):

    """
    Wrapper around the Esbuild command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, executable_search_paths, which):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type executable_search_paths: list
        :param executable_search_paths: List of paths to the NPM package binary utilities. This will
            be used to find embedded esbuild at runtime if present in the package

        :type which: aws_lambda_builders.utils.which
        :param which: Function to get paths which conform to the given mode on the PATH
            with the prepended additional search paths
        """
        self.osutils = osutils
        self.executable_search_paths = executable_search_paths
        self.which = which

    def esbuild_binary(self):
        """
        Finds the esbuild binary at runtime.

        The utility may be present as a package dependency of the Lambda project,
        or in the global path. If there is one in the Lambda project, it should
        be preferred over a global utility. The check has to be executed
        at runtime, since NPM dependencies will be installed by the workflow
        using one of the previous actions.
        """

        LOG.debug("checking for esbuild in: %s", self.executable_search_paths)
        binaries = self.which("esbuild", executable_search_paths=self.executable_search_paths)
        LOG.debug("potential esbuild binaries: %s", binaries)

        if binaries:
            return binaries[0]
        else:
            raise EsbuildExecutionError(message="cannot find esbuild")

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

        invoke_esbuild = [self.esbuild_binary()] + args

        LOG.debug("executing Esbuild: %s", invoke_esbuild)

        p = self.osutils.popen(invoke_esbuild, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise EsbuildExecutionError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()
