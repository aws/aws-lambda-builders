"""
Wrapper around calling npm through a subprocess.
"""

import logging
from typing import Dict, Optional

from aws_lambda_builders.workflows.nodejs_npm.exceptions import NpmExecutionError

LOG = logging.getLogger(__name__)


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
        self._project_root_cache: Dict[str, Optional[str]] = {}

    def resolve_project_root(self, cwd: str) -> Optional[str]:
        """
        Ask npm which directory it treats as the project root when it runs in ``cwd``, caching the answer.

        `npm prefix` walks up to the nearest directory holding a package.json, which for a workspace
        package is the monorepo root - where npm keeps the single lockfile and hoists node_modules to -
        and is the directory itself for any other package. Both the lockfile lookup that selects the
        install command and the link step that points the artifacts at the installed dependencies need
        that answer for the same directory, so it is resolved once per directory rather than per caller.

        Parameters
        ----------
        cwd : str
            the directory npm will run in

        Returns
        -------
        Optional[str]
            npm's project root, or None when npm could not be asked
        """
        if cwd not in self._project_root_cache:
            try:
                self._project_root_cache[cwd] = self.run(["prefix"], cwd=cwd).strip()
            except NpmExecutionError as ex:
                LOG.debug("NODEJS could not resolve the npm project root of %s: %s", cwd, ex)
                self._project_root_cache[cwd] = None

        return self._project_root_cache[cwd]

    def run(self, args, cwd=None):
        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to NPM

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.nodejs_npm.exceptions.NpmExecutionError:
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
