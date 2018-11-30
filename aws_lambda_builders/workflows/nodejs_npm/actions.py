"""
Action to resolve NodeJS dependencies using NPM
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .packager import NodejsNpmDependencyBuilder, PackagerError


class NodejsNpmBuildAction(BaseAction):

    NAME = 'ResolveDependencies'
    DESCRIPTION = "Installing dependencies from NPM"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, scratch_dir, manifest_path, runtime):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.runtime = runtime
        self.package_builder = NodejsNpmDependencyBuilder(runtime=runtime)

    def execute(self):
        try:
            self.package_builder.build_dependencies(
                self.artifacts_dir,
                self.scratch_dir,
                self.manifest_path
            )
        except PackagerError as ex:
            raise ActionFailedError(str(ex))
