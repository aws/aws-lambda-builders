"""
Wrapper around calling Cargo Lambda through a subprocess.
"""
import logging
import os
import subprocess

from .exceptions import CargoLambdaExecutionException
from .utils import OSUtils


LOG = logging.getLogger(__name__)


class SubprocessCargoLambda(object):
    """
    Wrapper around the Cargo Lambda command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, which, executable_search_paths=None, osutils=OSUtils()):
        """
        :type which: aws_lambda_builders.utils.which
        :param which: Function to get paths which conform to the given mode on the PATH
            with the prepended additional search paths

        :type executable_search_paths: list
        :param executable_search_paths: List of paths to the NPM package binary utilities. This will
            be used to find embedded esbuild at runtime if present in the package

        :type osutils: aws_lambda_builders.workflows.rust_cargo.actions.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation
        """
        self._which = which
        self._executable_search_paths = executable_search_paths
        self._osutils = osutils

    def check_cargo_lambda_installation(self):
        """
        Checks if Cargo Lambda is in the system

        :raises aws_lambda_builders.workflows.rust_cargo.exceptions.CargoLambdaExecutionException:
            when Cargo Lambda is not installed in the system to run the command.
        """

        LOG.debug("checking for cargo-lambda")
        binaries = self._which("cargo-lambda", executable_search_paths=self._executable_search_paths)
        LOG.debug("potential cargo-lambda binaries: %s", binaries)

        if binaries:
            return binaries[0]
        else:
            raise CargoLambdaExecutionException(
                message="Cannot find Cargo Lambda. "
                "Cargo Lambda must be installed on the host machine to use this feature. "
                "Follow the gettings started guide to learn how to install it: "
                "https://www.cargo-lambda.info/guide/getting-started.html"
            )

    def run(self, command, cwd):
        """
        Runs the build command.

        :type command: str
        :param args: Cargo Lambda command to run

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.rust_cargo.exceptions.CargoLambdaExecutionException:
            when Cargo Lambda is not installed in the system to run the command.

        :raises aws_lambda_builders.workflows.rust_cargo.exceptions.CargoLambdaExecutionException:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.
        """

        self.check_cargo_lambda_installation()

        LOG.debug("Executing cargo-lambda: %s", " ".join(command))
        if LOG.isEnabledFor(logging.DEBUG):
            if "RUST_LOG" not in os.environ:
                os.environ["RUST_LOG"] = "debug"
            LOG.debug("RUST_LOG environment variable set to `%s`", os.environ.get("RUST_LOG"))
        cargo_process = self._osutils.popen(
            command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=cwd,
        )
        out, err = cargo_process.communicate()
        output = out.decode("utf8").strip()
        if cargo_process.returncode != 0:
            error = err.decode("utf8").strip()
            LOG.debug("cargo-lambda STDOUT:\n\n%s\n\n", output)
            LOG.debug("cargo-lambda STDERR:\n\n%s\n\n", error)
            raise CargoLambdaExecutionException(message=error)

        return output
