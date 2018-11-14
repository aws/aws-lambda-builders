"""
Action to resolve Python dependencies using PIP
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .packager import PythonPipDependencyBuilder, PackagerError


class PythonPipBuildAction(BaseAction):

    NAME = 'PythonPipBuildAction'
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, manifest_path, runtime):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.package_builder = PythonPipDependencyBuilder()

    def execute(self):
        try:
            self.package_builder.build_dependencies(
                self.artifacts_dir,
                self.manifest_path,
                self.runtime,
            )
        except PackagerError as ex:
            raise ActionFailedError(str(ex))
