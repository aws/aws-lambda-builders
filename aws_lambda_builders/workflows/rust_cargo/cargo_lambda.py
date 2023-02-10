"""
Wrapper around calling Cargo Lambda through a subprocess.
"""
import io
import logging
import os
import shutil
import subprocess
import threading

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
        Parameters
        ----------
        which : aws_lambda_builders.utils.which
            Function to get paths which conform to the given mode on the PATH
            with the prepended additional search paths

        executable_search_paths : list, optional
            List of paths to the NPM package binary utilities. This will
            be used to find embedded esbuild at runtime if present in the package

        osutils : aws_lambda_builders.workflows.rust_cargo.utils.OSUtils, optional
            An instance of OS Utilities for file manipulation
        """
        self._which = which
        self._executable_search_paths = executable_search_paths
        self._osutils = osutils

    def check_cargo_lambda_installation(self):
        """
        Checks if Cargo Lambda is in the system

        Returns
        -------
        str
            Path to the cargo-lambda binary

        Raises
        ------
        CargoLambdaExecutionException:
            Raised when Cargo Lambda is not installed in the system to run the command.
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

        Parameters
        ----------
        command : str
            Cargo Lambda command to run

        cwd : str
            Directory where to execute the command (defaults to current dir)

        Returns
        -------
        str
            Text of the standard output from the command

        Raises
        ------
        CargoLambdaExecutionException:
            Raised when the command executes with a non-zero return code. The exception will
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
        stdout = ""
        # Create a buffer and use a thread to gather the stderr stream into the buffer
        stderr_buf = io.BytesIO()
        stderr_thread = threading.Thread(
            target=shutil.copyfileobj, args=(cargo_process.stderr, stderr_buf), daemon=True
        )
        stderr_thread.start()

        # Log every stdout line by iterating
        for line in cargo_process.stdout:
            decoded_line = line.decode("utf-8").strip()
            LOG.info(decoded_line)
            # Gather total stdout
            stdout += decoded_line

        # Wait for the process to exit and stderr thread to end.
        return_code = cargo_process.wait()
        stderr_thread.join()

        if return_code != 0:
            # Raise an Error with the appropriate value from the stderr buffer.
            raise CargoLambdaExecutionException(message=stderr_buf.getvalue().decode("utf8").strip())
        return stdout
