"""
Build a Go project using standard Go tooling
"""
import logging

from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.architecture import X86_64, ARM64
from aws_lambda_builders.utils import get_goarch

LOG = logging.getLogger(__name__)


class BuilderError(Exception):
    MESSAGE = "Builder Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class GoModulesBuilder(object):

    LANGUAGE = "go"

    def __init__(self, osutils, binaries, mode=BuildMode.RELEASE, architecture=X86_64):
        """Initialize a GoModulesBuilder.

        :type osutils: :class:`lambda_builders.utils.OSUtils`
        :param osutils: A class used for all interactions with the
            outside OS.

        :type binaries: dict
        :param binaries: A dict of language binaries

        :type architecture: str
        :param architecture: name of the type of architecture
        """
        self.osutils = osutils
        self.binaries = binaries
        self.mode = mode
        self.goarch = get_goarch(architecture)

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
        if self.mode and self.mode.lower() == BuildMode.DEBUG:
            LOG.debug("Debug build requested: Setting configuration to Debug")
            cmd += ["-gcflags", "all=-N -l"]
        cmd += ["-o", output_path, source_dir_path]

        p = self.osutils.popen(cmd, cwd=source_dir_path, env=env, stdout=self.osutils.pipe, stderr=self.osutils.pipe)
        out, err = p.communicate()

        if p.returncode != 0:
            raise BuilderError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()
