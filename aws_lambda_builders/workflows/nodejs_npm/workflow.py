"""
NodeJS NPM Workflow
"""
import logging

from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction, CopyDependenciesAction
from .actions import NodejsNpmPackAction, NodejsNpmInstallAction, NodejsNpmrcCopyAction, NodejsNpmrcCleanUpAction
from .utils import OSUtils
from .npm import SubprocessNpm

LOG = logging.getLogger(__name__)


class NodejsNpmWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that knows how to pack
    NodeJS projects using NPM.
    """

    NAME = "NodejsNpmBuilder"

    CAPABILITY = Capability(language="nodejs", dependency_manager="npm", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(NodejsNpmWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        subprocess_npm = SubprocessNpm(osutils)

        tar_dest_dir = osutils.joinpath(scratch_dir, "unpacked")
        tar_package_dir = osutils.joinpath(tar_dest_dir, "package")

        npm_pack = NodejsNpmPackAction(
            tar_dest_dir, scratch_dir, manifest_path, osutils=osutils, subprocess_npm=subprocess_npm
        )

        npm_copy_npmrc = NodejsNpmrcCopyAction(tar_package_dir, source_dir, osutils=osutils)

        self.actions = [
            npm_pack,
            npm_copy_npmrc,
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
        ]

        if self.download_dependencies:
            # installed the dependencies into artifact folder
            self.actions.append(NodejsNpmInstallAction(artifacts_dir, subprocess_npm=subprocess_npm))

            # if dependencies folder exists, copy dependencies into dependencies into dependencies folder
            if self.dependencies_dir:
                self.actions.append(CopyDependenciesAction(source_dir, artifacts_dir, self.dependencies_dir))
        else:
            # if dependencies folder exists and not download dependencies, simply copy the dependencies from the
            # dependencies folder to artifact folder
            if self.dependencies_dir:
                self.actions.append(CopySourceAction(self.dependencies_dir, artifacts_dir))
            else:
                LOG.info(
                    "download_dependencies is False and dependencies_dir is None. Copying the source files into the "
                    "artifacts directory. "
                )

        self.actions.append(NodejsNpmrcCleanUpAction(artifacts_dir, osutils=osutils))

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]
