"""
Build a Go project using standard Go tooling
"""
import logging
from pathlib import Path

from aws_lambda_builders.architecture import X86_64
from aws_lambda_builders.utils import get_goarch
from aws_lambda_builders.workflow import BuildMode

LOG = logging.getLogger(__name__)


class BuilderError(Exception):
    MESSAGE = "Builder Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class GoModulesBuilder(object):
    LANGUAGE = "go"

    def __init__(self, osutils, binaries, handler, mode=BuildMode.RELEASE, architecture=X86_64, trim_go_path=False):
        """Initialize a GoModulesBuilder.

        :type osutils: :class:`lambda_builders.utils.OSUtils`
        :param osutils: A class used for all interactions with the
            outside OS.

        :type binaries: dict
        :param binaries: A dict of language binaries

        :type architecture: str
        :param architecture: name of the type of architecture

        :type trim_go_path: bool
        :param trim_go_path: should go build use -trimpath flag
        """
        self.osutils = osutils
        self.binaries = binaries
        self.mode = mode
        self.goarch = get_goarch(architecture)
        self.trim_go_path = trim_go_path
        self.handler = handler

    def build(self, source_dir_path, output_path):
        """Builds a go project onto an output path.

        :type source_dir_path: str
        :param source_dir_path: Directory with the source files.

        :type output_path: str
        :param output_path: Filename to write the executable output to.
        """
        env = {}
        env.update(self.osutils.environ)
        env.update({"GOOS": "linux", "GOARCH": self.goarch})
        runtime_path = self.binaries[self.LANGUAGE].binary_path
        cmd = [runtime_path, "build"]
        if self.trim_go_path:
            LOG.debug("Trimpath requested: Setting go build configuration to -trimpath")
            cmd += ["-trimpath"]
        if self.mode and self.mode.lower() == BuildMode.DEBUG:
            LOG.debug("Debug build requested: Setting configuration to Debug")
            cmd += ["-gcflags", "all=-N -l"]
        cmd += ["-o", output_path, source_dir_path]

        p = self.osutils.popen(cmd, cwd=source_dir_path, env=env, stdout=self.osutils.pipe, stderr=self.osutils.pipe)
        out, err = p.communicate()

        if p.returncode != 0:
            LOG.debug(err.decode("utf8").strip())
            LOG.debug("Go files not found. Attempting to build for Go files in a different directory")
            process, p_out, p_err = self._attempt_to_build_from_handler(cmd, source_dir_path, env)
            if process.returncode != 0:
                raise BuilderError(message=p_err.decode("utf8").strip())
            return p_out.decode("utf8").strip()

        return out.decode("utf8").strip()

    def _attempt_to_build_from_handler(self, cmd: list, source_dir_path: str, env: dict):
        """Builds Go files when package/source file in different directory

        :type cmd: list
        :param cmd: list of commands.

        :type source_dir_path: str
        :param source_dir_path: path to the source file/package.

        :type env: dict
        :param env: dictionary with environment variables.
        """

        # Path to the source directory for Go files in a diff directory
        cmd[-1] = str(Path(source_dir_path, self.handler))
        LOG.debug(
            "Go files not found at CodeUri %s . Descending into sub-directories to find the handler: %s",
            source_dir_path,
            cmd[-1],
        )
        p = self.osutils.popen(cmd, cwd=source_dir_path, env=env, stdout=self.osutils.pipe, stderr=self.osutils.pipe)
        out, err = p.communicate()
        return p, out, err
