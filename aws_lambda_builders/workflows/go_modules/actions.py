"""
Action to build a Go project using standard Go tooling
"""

from shutil import copy2

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
            self.builder.build(
                self.source_dir,
                self.output_path,
            )
        except BuilderError as ex:
            raise ActionFailedError(str(ex))


class CopyGoSumAction(BaseAction):

    NAME = "Copy go.sum"
    DESCRIPTION = "Copy go.sum file into artifact dir"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, output_path, osutils):
        self.source_dir = source_dir
        self.output_path = output_path
        self.osutils = osutils

    def execute(self):
        go_sum_file = self.osutils.joinpath(self.source_dir, "go.sum")
        copy2(go_sum_file, self.output_path)
