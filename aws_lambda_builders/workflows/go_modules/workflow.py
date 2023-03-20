"""
Go Modules Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability

from .actions import GoModulesBuildAction
from .builder import GoModulesBuilder
from .utils import OSUtils
from .validator import GoRuntimeValidator


class GoModulesWorkflow(BaseWorkflow):
    NAME = "GoModulesBuilder"

    CAPABILITY = Capability(language="go", dependency_manager="modules", application_framework=None)

    DEFAULT_BUILD_DIR = BuildDirectory.SOURCE
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.EXCLUSIVELY_SUPPORTED

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
        trim_go_path = options.get("trim_go_path", False)

        output_path = osutils.joinpath(artifacts_dir, handler)

        builder = GoModulesBuilder(
            osutils,
            binaries=self.binaries,
            handler=handler,
            mode=mode,
            architecture=self.architecture,
            trim_go_path=trim_go_path,
        )

        self.actions = [GoModulesBuildAction(source_dir, output_path, builder)]

    def get_validators(self):
        return [GoRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
