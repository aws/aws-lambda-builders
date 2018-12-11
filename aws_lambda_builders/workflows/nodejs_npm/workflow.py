"""
NodeJS NPM Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from .actions import NodejsNpmPackAction, NodejsNpmInstallAction
from .utils import OSUtils
from .npm import SubprocessNpm


class NodejsNpmWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that knows how to pack
    NodeJS projects using NPM.
    """
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

        subprocess_npm = SubprocessNpm(osutils)

        tar_dest_dir = osutils.joinpath(scratch_dir, 'unpacked')
        tar_package_dir = osutils.joinpath(tar_dest_dir, 'package')

        npm_pack = NodejsNpmPackAction(tar_dest_dir,
                                       scratch_dir,
                                       manifest_path,
                                       osutils=osutils,
                                       subprocess_npm=subprocess_npm)

        npm_install = NodejsNpmInstallAction(artifacts_dir,
                                             subprocess_npm=subprocess_npm)
        self.actions = [
            npm_pack,
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
            npm_install,
        ]
