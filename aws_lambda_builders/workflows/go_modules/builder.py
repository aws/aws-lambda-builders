"""
Build a Go project using standard Go tooling
"""
import logging


LOG = logging.getLogger(__name__)


class BuilderError(Exception):
    MESSAGE = "Builder Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class GoModulesBuilder(object):
    def __init__(self, osutils):
        """Initialize a GoModulesBuilder.

        :type osutils: :class:`lambda_builders.utils.OSUtils`
        :param osutils: A class used for all interactions with the
            outside OS.
        """
        self.osutils = osutils

    def build(self, source_dir_path, artifacts_dir_path, executable_name):
        """Builds a go project into an artifact directory.

        :type source_dir_path: str
        :param source_dir_path: Directory with the source files.

        :type artifacts_dir_path: str
        :param artifacts_dir_path: Directory to write dependencies into.

        :type executable_name: str
        :param executable_name: Name of the executable to create from the build.
        """
        env = {}
        env.update(self.osutils.environ)
        env.update({"GOOS": "linux", "GOARCH": "amd64"})
        cmd = ["go", "build", "-o", self.osutils.joinpath(artifacts_dir_path, executable_name), source_dir_path]

        p = self.osutils.popen(
            cmd,
            cwd=source_dir_path,
            env=env,
            stdout=self.osutils.pipe,
            stderr=self.osutils.pipe,
        )
        out, err = p.communicate()

        if p.returncode != 0:
            raise BuilderError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()
