"""
Wrapper around calls to bundler through a subprocess.
"""

import logging

LOG = logging.getLogger(__name__)


class BundlerExecutionError(Exception):
    """
    Exception raised when Bundler fails.
    Will encapsulate error output from the command.
    """

    MESSAGE = "Bundler Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessBundler(object):
    """
    Wrapper around the Bundler command line utility, encapsulating
    execution results.
    """

    def __init__(self, osutils, bundler_exe=None):
        self.osutils = osutils
        if bundler_exe is None:
            if osutils.is_windows():
                bundler_exe = "bundler.bat"
            else:
                bundler_exe = "bundle"

        self.bundler_exe = bundler_exe

    def run(self, args, cwd=None):
        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_bundler = [self.bundler_exe] + args

        LOG.debug("executing Bundler: %s", invoke_bundler)

        p = self.osutils.popen(invoke_bundler, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd)

        out, _ = p.communicate()

        if p.returncode != 0:
            # Bundler has relevant information in stdout, not stderr.
            raise BundlerExecutionError(message=out.decode("utf8").strip())

        return out.decode("utf8").strip()
