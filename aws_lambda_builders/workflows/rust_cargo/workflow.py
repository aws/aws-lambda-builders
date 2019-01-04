"""
Python PIP Workflow
"""
import os

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction

from .actions import RustCargoBuildAction, CopyAndRenameExecutableAction, CargoValidator


class RustCargoWorkflow(BaseWorkflow):

    NAME = "RustCargoWorkflow"
    CAPABILITY = Capability(language="rust",
                            dependency_manager="cargo",
                            application_framework=None)

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 runtime=None, **kwargs):

        super(RustCargoWorkflow, self).__init__(source_dir,
                                                artifacts_dir,
                                                scratch_dir,
                                                manifest_path,
                                                runtime=runtime,
                                                **kwargs)

        self.actions = [
            CargoValidator(source_dir, manifest_path, runtime),
            RustCargoBuildAction(source_dir, manifest_path, runtime),
            CopyAndRenameExecutableAction(source_dir, self.artifacts_dir, manifest_path, runtime),
        ]
