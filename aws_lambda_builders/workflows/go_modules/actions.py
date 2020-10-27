"""
Action to build a Go project using standard Go tooling
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .builder import BuilderError


class GoModulesBuildAction(BaseAction):

    NAME = "Build"
    DESCRIPTION = "Building Go package with Go Modules"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, output_path, builder):
        self.source_dir = source_dir
        self.output_path = output_path
        self.builder = builder

    def execute(self):
        try:
            self.builder.build(self.source_dir, self.output_path)
        except BuilderError as ex:
            raise ActionFailedError(str(ex))
