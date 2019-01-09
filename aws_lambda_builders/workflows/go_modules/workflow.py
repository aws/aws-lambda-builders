"""
Go Modules Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability

from .actions import GoModulesBuildAction
from .builder import GoModulesBuilder
from .path_resolver import GoPathResolver
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

        options = kwargs.get("options") or {}
        handler = options.get("handler", None)

        output_path = osutils.joinpath(artifacts_dir, handler)

        builder = GoModulesBuilder(osutils, runtime_path=self.get_executable())
        self.actions = [
            GoModulesBuildAction(source_dir, output_path, builder),
        ]

    def get_executable(self):
        return GoPathResolver(runtime=self.runtime).exec_path

    def get_validator(self):
        return GoRuntimeValidator(runtime=self.runtime, runtime_path=self.get_executable())
