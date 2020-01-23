"""
Actions for Go dependency resolution with dep
"""

import logging
import os

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError

from .subproc_exec import ExecutionError


LOG = logging.getLogger(__name__)


class DepEnsureAction(BaseAction):

    """
    A Lambda Builder Action which runs dep to install dependencies from Gopkg.toml
    """

    NAME = "DepEnsure"
    DESCRIPTION = "Ensures all dependencies are installed for a project"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, base_dir, subprocess_dep):
        super(DepEnsureAction, self).__init__()

        self.base_dir = base_dir
        self.subprocess_dep = subprocess_dep

    def execute(self):
        try:
            self.subprocess_dep.run(["ensure"], cwd=self.base_dir)
        except ExecutionError as ex:
            raise ActionFailedError(str(ex))


class GoBuildAction(BaseAction):

    """
    A Lambda Builder Action which runs `go build` to create a binary
    """

    NAME = "GoBuild"
    DESCRIPTION = "Builds final binary"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, base_dir, source_path, output_path, subprocess_go, env=None):
        super(GoBuildAction, self).__init__()

        self.base_dir = base_dir
        self.source_path = source_path
        self.output_path = output_path

        self.subprocess_go = subprocess_go
        self.env = env if not env is None else {}

    def execute(self):
        env = self.env
        env.update({"GOOS": "linux", "GOARCH": "amd64"})

        try:
            self.subprocess_go.run(["build", "-o", self.output_path, self.source_path], cwd=self.source_path, env=env)
        except ExecutionError as ex:
            raise ActionFailedError(str(ex))
