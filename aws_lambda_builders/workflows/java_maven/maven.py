"""
Wrapper around calls to Maven through a subprocess.
"""

import logging
import subprocess

LOG = logging.getLogger(__name__)


class MavenExecutionError(Exception):
    MESSAGE = "Maven Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessMaven(object):
    def __init__(self, maven_binary, os_utils=None):
        if maven_binary is None:
            raise ValueError("Must provide Maven BinaryPath")
        self.maven_binary = maven_binary
        if os_utils is None:
            raise ValueError("Must provide OSUtils")
        self.os_utils = os_utils

    def build(self, scratch_dir):
        args = ["clean", "install"]
        ret_code, stdout, _ = self._run(args, scratch_dir)

        LOG.debug("Maven logs: %s", stdout.decode("utf8").strip())

        if ret_code != 0:
            raise MavenExecutionError(message=stdout.decode("utf8").strip())

    def copy_dependency(self, scratch_dir):
        include_scope = "runtime"
        LOG.debug("Running copy_dependency with scope: %s", include_scope)
        args = ["dependency:copy-dependencies", f"-DincludeScope={include_scope}", "-Dmdep.prependGroupId=true"]
        ret_code, stdout, _ = self._run(args, scratch_dir)

        if ret_code != 0:
            raise MavenExecutionError(message=stdout.decode("utf8").strip())

    def _run(self, args, cwd=None):
        p = self.os_utils.popen(
            [self.maven_binary.binary_path] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr
