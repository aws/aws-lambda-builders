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
        working_directory = options.get("working_directory")

        if working_directory is None:
            working_directory = scratch_dir
        else:
            if self.os_utils.isabspath(working_directory):
                # Working directory should be relative to the source_dir, so when we copy the source_dir to scratch_dir
                # the working directory value is still valid
                working_directory = self.os_utils.relpath(working_directory, source_dir)

            # join the working directory to the scratch_dir
            working_directory = self.os_utils.normpath(self.os_utils.join_relpath(working_directory, scratch_dir))

        if working_directory is None:
            working_directory = scratch_dir

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
            working_directory=working_directory,
        )

        self.actions = [CopySourceAction(source_dir, scratch_dir, excludes=self.EXCLUDED_FILES), make_action]

    def get_resolvers(self):
        return [PathResolver(runtime="provided", binary="make", executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [CustomMakeRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
