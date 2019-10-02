"""
Go Modules Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability

from .actions import GoModulesBuildAction
from .builder import GoModulesBuilder
from .validator import GoRuntimeValidator
from .utils import OSUtils


class GoModulesWorkflow(BaseWorkflow):

    NAME = "GoModulesBuilder"

    CAPABILITY = Capability(language="go",
                            dependency_manager="modules",
                            application_framework=None)

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 runtime=None,
                 osutils=None,
                 **kwargs):

        super(GoModulesWorkflow, self).__init__(
            source_dir,
            artifacts_dir,
            scratch_dir,
            manifest_path,
            runtime=runtime,
            **kwargs)

        if osutils is None:
            osutils = OSUtils()

        output_path = osutils.joinpath(artifacts_dir, source_dir)

        builder = GoModulesBuilder(osutils, binaries=self.binaries)
        self.actions = [
            GoModulesBuildAction(source_dir, output_path, builder),
        ]

    def get_validators(self):
        return [GoRuntimeValidator(runtime=self.runtime)]
