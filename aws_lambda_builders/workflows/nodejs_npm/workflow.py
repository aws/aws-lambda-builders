"""
NodeJS NPM Workflow
"""

import hashlib

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction

from .actions import NodejsNpmPackAction, NodejsNpmInstallAction
from .utils import OSUtils


def unique_dir(manifest_path):
    md5 = hashlib.md5()
    md5.update(manifest_path.encode('utf8'))
    return md5.hexdigest()


class NodejsNpmWorkflow(BaseWorkflow):

    NAME = "NodejsNpmBuilder"

    CAPABILITY = Capability(language="nodejs",
                            dependency_manager="npm",
                            application_framework=None)

    EXCLUDED_FILES = (".aws-sam")

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 runtime=None,
                 osutils=None,
                 **kwargs):

        super(NodejsNpmWorkflow, self).__init__(source_dir,
                                                artifacts_dir,
                                                scratch_dir,
                                                manifest_path,
                                                runtime=runtime,
                                                **kwargs)

        if osutils is None:
            osutils = OSUtils()

        tar_dest_dir = osutils.joinpath(scratch_dir, unique_dir(manifest_path))
        tar_package_dir = osutils.joinpath(tar_dest_dir, 'package')

        self.actions = [
            NodejsNpmPackAction(tar_dest_dir, scratch_dir, manifest_path, runtime),
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
            NodejsNpmInstallAction(artifacts_dir, scratch_dir, manifest_path, runtime)
        ]
