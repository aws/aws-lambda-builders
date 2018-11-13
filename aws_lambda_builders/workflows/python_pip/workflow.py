"""
Python PIP Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction

from .actions import PythonPipBuildAction


class PythonPipWorkflow(BaseWorkflow):

    NAME = "PythonPipWorkflow"
    CAPABILITY = Capability(language="python",
                            dependency_manager="pip",
                            application_framework=None)

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 runtime=None, **kwargs):

        super(PythonPipWorkflow, self).__init__(source_dir,
                                                artifacts_dir,
                                                scratch_dir,
                                                manifest_path,
                                                runtime=runtime,
                                                **kwargs)

        self.actions = [
            PythonPipBuildAction(artifacts_dir, manifest_path, runtime),
            CopySourceAction(source_dir, artifacts_dir),
        ]
