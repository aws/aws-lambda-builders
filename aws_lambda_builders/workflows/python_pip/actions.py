from aws_lambda_builders.actions import BaseAction
from .packager import PythonPipDependencyBuilder


class PythonPipBuildAction(BaseAction):

    NAME = 'PythonPipBuildAction'

    def __init__(self, artifacts_dir, manifest_path, runtime):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.package_builder = PythonPipDependencyBuilder()

    def execute(self):
        self.package_builder.build_dependencies(
            self.artifacts_dir,
            self.manifest_path,
            self.runtime,
        )
