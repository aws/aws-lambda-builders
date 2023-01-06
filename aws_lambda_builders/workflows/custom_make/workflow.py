"""
ProvidedMakeWorkflow
"""
from aws_lambda_builders.workflows.custom_make.validator import CustomMakeRuntimeValidator
from aws_lambda_builders.workflow import BaseWorkflow, Capability, BuildInSourceSupport
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

    BUILD_IN_SOURCE_BY_DEFAULT = False
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(CustomMakeWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        self.os_utils = OSUtils()

        options = kwargs.get("options") or {}
        build_in_source = kwargs.get("build_in_source")

        build_logical_id = options.get("build_logical_id", None)
        if not build_logical_id:
            raise WorkflowFailedError(
                workflow_name=self.NAME,
                action_name=None,
                reason="Build target {} is not found!".format(build_logical_id),
            )

        subprocess_make = SubProcessMake(make_exe=self.binaries["make"].binary_path, osutils=self.os_utils)

        # an explicitly definied working directory should take precedence
        working_directory = options.get("working_directory") or self._select_working_directory(
            source_dir, scratch_dir, build_in_source
        )

        make_action = CustomMakeAction(
            artifacts_dir,
            manifest_path,
            osutils=self.os_utils,
            subprocess_make=subprocess_make,
            build_logical_id=build_logical_id,
            working_directory=working_directory,
        )

        self.actions = []

        if not self.build_in_source:
            # if we're building on scratch_dir, we have to first copy the source there
            self.actions.append(CopySourceAction(source_dir, scratch_dir, excludes=self.EXCLUDED_FILES))

        self.actions.append(make_action)

    def _select_working_directory(self, source_dir: str, scratch_dir: str, build_in_source: bool):
        """
        Returns the directory where the make action should be executed
        """
        return source_dir if build_in_source else scratch_dir

    def get_resolvers(self):
        return [PathResolver(runtime="provided", binary="make", executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [CustomMakeRuntimeValidator(runtime=self.runtime, architecture=self.architecture)]
