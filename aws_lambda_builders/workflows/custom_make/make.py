"""
Wrapper around calling make through a subprocess.
"""
import io
import logging
import shutil
import sys
import threading

LOG = logging.getLogger(__name__)


class MakeExecutionError(Exception):

    """
    Exception raised in case Make execution fails.
    It will pass on the standard error output from the Make console.
    """

    MESSAGE = "Make Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubProcessMake(object):

    """
    Wrapper around the Make command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, make_exe=None):
        """
        :type osutils: aws_lambda_builders.workflows.custom_make.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type make_exe: str
        :param make_exe: Path to the Make binary. If not set,
            the default executable path make will be used
        """
        self.osutils = osutils

        if make_exe is None:
            if osutils.is_windows():
                make_exe = "make.exe"
            else:
                make_exe = "make"

        self.make_exe = make_exe

    def run(self, args, env=None, cwd=None):
        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to Make

        :type env: dict
        :param env : environment variables dictionary to be passed into subprocess

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.custom_make.make.MakeExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_make = [self.make_exe] + args

        LOG.debug("executing Make: %s", invoke_make)

        p = self.osutils.popen(invoke_make, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd, env=env)

        # Create a stdout variable that will contain the final stitched stdout result
        stdout = ""
        # Create a buffer and use a thread to gather the stderr stream into the buffer
        stderr_buf = io.BytesIO()
        stderr_thread = threading.Thread(target=shutil.copyfileobj, args=(p.stderr, stderr_buf), daemon=True)
        stderr_thread.start()

        # Log every stdout line by iterating
        for line in p.stdout:
            # Writing to stderr instead of using LOG.info
            # since the logger library does not include ANSI
            # formatting characters in the output
            #
            # stderr is used since stdout appears to be reserved
            # for command responses
            sys.stderr.buffer.write(line)
            sys.stderr.flush()

            # Gather total stdout
            decoded_line = line.decode("utf-8").strip()
            stdout += decoded_line

        # Wait for the process to exit and stderr thread to end.
        return_code = p.wait()
        stderr_thread.join()

        if return_code != 0:
            # Raise an Error with the appropriate value from the stderr buffer.
            raise MakeExecutionError(message=stderr_buf.getvalue().decode("utf8").strip())

        return stdout
