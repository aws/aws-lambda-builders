"""
Wrapper around calls to bundler through a subprocess.
"""

import logging
from os import linesep

LOG = logging.getLogger(__name__)

"""
Bundler error codes can be found here:
https://github.com/rubygems/bundler/blob/3f0638c6c8d340c2f2405ecb84eb3b39c433e36e/lib/bundler/errors.rb#L36
"""
GEMFILE_NOT_FOUND = 10


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

        out, err = p.communicate()

        if p.returncode != 0:
            if p.returncode == GEMFILE_NOT_FOUND:
                LOG.warning("Gemfile not found. Continuing the build without dependencies.")

                # Clean up '.bundle' dir that gets generated before the build fails
                check_dir = self.osutils.get_bundle_dir(cwd)
                if self.osutils.directory_exists(check_dir):
                    self.osutils.remove_directory(check_dir)
            else:
                # Bundler can contain information in both stdout and stderr so we check and log both
                err_str = err.decode("utf8").strip()
                out_str = out.decode("utf8").strip()
                if out_str and err_str:
                    message_out = f"{out_str}{linesep}{err_str}"
                    LOG.debug(f"Bundler output: {out_str}")
                    LOG.debug(f"Bundler error: {err_str}")
                elif out_str:
                    message_out = out_str
                    LOG.debug(f"Bundler output: {out_str}")
                else:
                    message_out = err_str
                    LOG.debug(f"Bundler error: {err_str}")
                raise BundlerExecutionError(message=message_out)

        return out.decode("utf8").strip()
