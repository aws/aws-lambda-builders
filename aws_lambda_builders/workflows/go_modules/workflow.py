"""
Go Modules Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction

from .actions import GoModulesBuildAction
from .builder import GoModulesBuilder
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

        executable_name = osutils.basename(source_dir)
        builder = GoModulesBuilder(osutils)
        self.actions = [
            GoModulesBuildAction(source_dir, artifacts_dir, executable_name, builder),
            CopySourceAction(source_dir, artifacts_dir, only=[executable_name]),
        ]
