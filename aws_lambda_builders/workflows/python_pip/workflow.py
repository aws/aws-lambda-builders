from aws_lambda_builders.workflows import BaseWorkflow
from aws_lambda_builders.actions import CopySourceAction

from .actions import PythonPipBuildAction


class PythonPipWorkflow(BaseWorkflow):
    def __init__(self, *args, **kwargs):
        super(PythonPipWorkflow, self).__init__(*args, **kwargs)
        # TODO if the parent class just has a self.ACTIONS  that it uses we can
        # just override that instead of needing to override __init__
        self.actions= [
            PythonPipBuildAction,
            CopySourceAction,
        ]
