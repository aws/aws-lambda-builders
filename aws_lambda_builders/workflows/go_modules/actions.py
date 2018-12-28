"""
Action to build a Go project using standard Go tooling
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .builder import BuilderError


class GoModulesBuildAction(BaseAction):

    NAME = "Build"
    DESCRIPTION = "Building Go package with Go Modules"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, source_dir, artifacts_dir, executable_name, builder):
        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.executable_name = executable_name
        self.builder = builder

    def execute(self):
        try:
            self.builder.build(
                self.source_dir,
                self.artifacts_dir,
                self.executable_name
            )
        except BuilderError as ex:
            raise ActionFailedError(str(ex))
