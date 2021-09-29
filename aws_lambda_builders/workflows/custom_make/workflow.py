"""
ProvidedMakeWorkflow
"""
from aws_lambda_builders.workflows.custom_make.validator import CustomMakeRuntimeValidator
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.path_resolver import PathResolver
from .actions import CustomMakeAction
from .utils import OSUtils
from .make import SubProcessMake
from ...exceptions import WorkflowFailedError


class CustomMakeWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow for provided runtimes based on make.
    """

    NAME = "CustomMakeBuilder"

    CAPABILITY = Capability(language="provided", dependency_manager=None, application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(CustomMakeWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        self.os_utils = OSUtils()

        # Find the logical id of the function to be built.
        options = kwargs.get("options") or {}
        build_logical_id = options.get("build_logical_id", None)

        if not build_logical_id:
            raise WorkflowFailedError(
                workflow_name=self.NAME,
                action_name=None,
                reason="Build target {} is not found!".format(build_logical_id),
            )

        subprocess_make = SubProcessMake(make_exe=self.binaries["make"].binary_path, osutils=self.os_utils)

        make_action = CustomMakeAction(
            artifacts_dir,
            scratch_dir,
            manifest_path,
            osutils=self.os_utils,
            subprocess_make=subprocess_make,
            build_logical_id=build_logical_id,
        )

        self.actions = [CopySourceAction(source_dir, scratch_dir, excludes=self.EXCLUDED_FILES), make_action]

    def get_resolvers(self):
        return [PathResolver(runtime="provided", binary="make", executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [CustomMakeRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
