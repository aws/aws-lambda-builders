"""
Actions for Go dependency resolution with dep
"""

import logging
import os

from shutil import copyfile

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError

from .exec import ExecutionError


LOG = logging.getLogger(__name__)

class CopyFileAction(BaseAction):

    """
    Copies a file to the source dir
    """

    NAME = "CopyFile"
    DESCRIPTION = "Copies a file to source directory"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, manifest_path, source_dir):
        super(CopyFileAction, self).__init__()

        self.manifest_path = manifest_path
        self.source_dir = source_dir

    def execute(self):
        manifest_name = os.path.basename(self.manifest_path)

        try:
            copyfile(self.manifest_path, os.path.join(self.source_dir, manifest_name))
        except OSError as ex:
            raise ActionFailedError(str(ex))

class DepEnsureAction(BaseAction):

    """
    A Lambda Builder Action which runs dep to install dependencies from Gopkg.toml
    """

    NAME = "DepEnsure"
    DESCRIPTION = "Ensures all dependencies are installed for a project"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, go_dir, source_dir, subprocess_dep):
        super(DepEnsureAction, self).__init__()

        self.go_dir = go_dir
        self.source_dir = source_dir
        self.subprocess_dep = subprocess_dep

    def execute(self):
        env = {"GOPATH": self.go_dir, "PATH": os.environ["PATH"]}

        LOG.debug("Environment variables: {}".format(env))

        try:
            self.subprocess_dep.run(["ensure", "-v"],
                                    cwd=self.source_dir,
                                    env=env)
        except ExecutionError as ex:
            raise ActionFailedError(str(ex))

class GoBuildAction(BaseAction):

    """
    A Lambda Builder Action which runs `go build` to create a binary
    """

    NAME = "GoBuild"
    DESCRIPTION = "Builds final binary"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, go_dir, source_dir, handler, subprocess_go):
        super(GoBuildAction, self).__init__()

        self.go_dir = go_dir
        self.source_dir = source_dir
        self.handler = handler
        self.subprocess_go = subprocess_go

    def execute(self):
        env = {"GOPATH": self.go_dir, "PATH": os.environ["PATH"], "GOOS": "linux", "GOARCH": "amd64"}

        LOG.debug("Environment variables: {}".format(env))

        try:
            self.subprocess_go.run(["build", "-o", self.handler],
                                    cwd=self.source_dir,
                                    env=env)
        except ExecutionError as ex:
            raise ActionFailedError(str(ex))
