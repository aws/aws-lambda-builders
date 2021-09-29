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

    CAPABILITY = Capability(language="go", dependency_manager="modules", application_framework=None)

    def __init__(
        self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, mode=None, **kwargs
    ):

        super(GoModulesWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        options = kwargs.get("options") or {}
        handler = options.get("artifact_executable_name", None)

        output_path = osutils.joinpath(artifacts_dir, handler)

        builder = GoModulesBuilder(osutils, binaries=self.binaries, mode=mode, architecture=self.architecture)
        self.actions = [GoModulesBuildAction(source_dir, output_path, builder)]

    def get_validators(self):
        return [GoRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
