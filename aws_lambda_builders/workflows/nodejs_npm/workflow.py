"""
NodeJS NPM Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability

from .actions import NodejsNpmPackAction, NodejsNpmInstallAction


class NodejsNpmWorkflow(BaseWorkflow):

    NAME = "NodejsNpmBuilder"

    CAPABILITY = Capability(language="nodejs",
                            dependency_manager="npm",
                            application_framework=None)

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
            NodejsNpmPackAction(artifacts_dir, scratch_dir, manifest_path, runtime),
            NodejsNpmInstallAction(artifacts_dir, scratch_dir, manifest_path, runtime)
        ]
