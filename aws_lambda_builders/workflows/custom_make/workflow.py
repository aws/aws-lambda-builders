"""
ProvidedMakeWorkflow
"""
from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability
from aws_lambda_builders.workflows.custom_make.validator import CustomMakeRuntimeValidator

from ...exceptions import WorkflowFailedError
from .actions import CustomMakeAction
from .make import SubProcessMake
from .utils import OSUtils


class CustomMakeWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow for provided runtimes based on make.
    """

    NAME = "CustomMakeBuilder"

    CAPABILITY = Capability(language="provided", dependency_manager=None, application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):
        super(CustomMakeWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        self.os_utils = OSUtils()

        options = kwargs.get("options") or {}

        build_logical_id = options.get("build_logical_id", None)
        if not build_logical_id:
            raise WorkflowFailedError(
                workflow_name=self.NAME,
                action_name=None,
                reason="Build target {} is not found!".format(build_logical_id),
            )

        subprocess_make = SubProcessMake(make_exe=self.binaries["make"].binary_path, osutils=self.os_utils)

        # an explicitly defined working directory should take precedence
        working_directory = options.get("working_directory") or self.build_dir

        make_action = CustomMakeAction(
            artifacts_dir,
            manifest_path,
            osutils=self.os_utils,
            subprocess_make=subprocess_make,
            build_logical_id=build_logical_id,
            working_directory=working_directory,
        )

        self.actions = []

        if self.build_dir != source_dir:
            # if we're not building in the source directory, we have to first copy the source
            self.actions.append(CopySourceAction(source_dir, self.build_dir, excludes=self.EXCLUDED_FILES))

        self.actions.append(make_action)

    def get_resolvers(self):
        return [PathResolver(runtime="provided", binary="make", executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [CustomMakeRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
