"""
NodeJS NPM Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction

from .actions import NodejsNpmInstallAction


class NodejsNpmWorkflow(BaseWorkflow):

    NAME = "NodejsNpmBuilder"

    CAPABILITY = Capability(language="nodejs",
                            dependency_manager="npm",
                            application_framework=None)

    # Common source files to exclude from build artifacts output
    # note that NPM will ignore most of the garbage anyway
    EXCLUDED_FILES = (
                      ".aws-sam", ".chalice"
                     )

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 runtime=None, **kwargs):

        super(NodejsNpmWorkflow, self).__init__(source_dir,
                                                artifacts_dir,
                                                scratch_dir,
                                                manifest_path,
                                                runtime=runtime,
                                                **kwargs)

        self.actions = [
            CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
            NodejsNpmInstallAction(artifacts_dir, scratch_dir, manifest_path, runtime)
        ]
