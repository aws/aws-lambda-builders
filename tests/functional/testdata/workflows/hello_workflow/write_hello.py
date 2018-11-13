"""
Provides a test workflow and action that writes a file to artifacts called hello.txt
"""

import os

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import BaseAction, Purpose


class WriteHelloAction(BaseAction):
    """
    Sample test action that writes a file to the artifacts directory
    """

    NAME = "WriteHelloAction"
    PURPOSE = Purpose.COPY_SOURCE
    DESCRIPTION = "Write an file to artifacts directory"

    FILENAME = "hello.txt"
    CONTENTS = "Hello World"

    def __init__(self, artifacts_dir):
        self.artifacts_dir = artifacts_dir

    def execute(self):
        path = os.path.join(self.artifacts_dir, self.FILENAME)

        with open(path, "w") as fp:
            fp.write(self.CONTENTS)


class WriteHelloWorkflow(BaseWorkflow):

    NAME = "WriteHelloWorkflow"
    CAPABILITY = Capability(language="test", dependency_manager="test", application_framework="test")

    def __init__(self, source_dir, artifacts_dir, *args, **kwargs):
        super(WriteHelloWorkflow, self).__init__(source_dir, artifacts_dir, *args, **kwargs)

        self.actions = [
            WriteHelloAction(artifacts_dir)
        ]

