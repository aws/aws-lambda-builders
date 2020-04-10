"""
ProvidedMakeWorkflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from .actions import ProvidedMakeAction
from .make_resolver import MakeResolver
from .utils import OSUtils
from .make import SubProcessMake


class ProvidedMakeWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow for provided runtimes based on make.
    """

    NAME = "ProvidedMakeBuilder"

    CAPABILITY = Capability(language="provided", dependency_manager=None, application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(ProvidedMakeWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        self.os_utils = OSUtils()

        options = kwargs.get("options") or {}
        build_logical_id = options.get("build_logical_id", None)

        subprocess_make = SubProcessMake(make_exe=self.binaries['make'].binary_path, osutils=self.os_utils)

        make_action = ProvidedMakeAction(
            artifacts_dir,
            scratch_dir, manifest_path, osutils=osutils, subprocess_make=subprocess_make, build_logical_id=build_logical_id
        )

        self.actions = [
            CopySourceAction(source_dir, scratch_dir, excludes=self.EXCLUDED_FILES),
            make_action
        ]

    def get_resolvers(self):
        return [MakeResolver(executable_search_paths=self.executable_search_paths)]
