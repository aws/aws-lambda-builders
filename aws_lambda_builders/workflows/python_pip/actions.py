from aws_lambda_builders.actions import BaseAction
from .packager import PythonPipDependencyBuilder

class PythonPipBuildAction(BaseAction):

    NAME = 'PythonPipBuildAction'

    def execute(self):
        # TODO still needs to be worked out how these are plumbed through from the workflow
        # to the underlying action. Specifically I am using self.<value> on the action however
        # currently the workflow does not set these properties, nor does it pass them through
        # the execute call.
        package_builder = PythonPipDependencyBuilder()
        package_builder.build_dependencies(
            self.artifacts_dir,
            self.manifest_path,
            self.runtime,
        )
