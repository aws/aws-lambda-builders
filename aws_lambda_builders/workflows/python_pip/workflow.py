from aws_lambda_builders.workflow import BaseWorkflow
from aws_lambda_builders.actions import CopySourceAction

from .actions import PythonPipBuildAction


class PythonPipWorkflow(BaseWorkflow):

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
