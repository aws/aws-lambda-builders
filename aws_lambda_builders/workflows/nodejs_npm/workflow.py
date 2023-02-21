"""
NodeJS NPM Workflow
"""

import logging

from aws_lambda_builders.actions import (
    CleanUpAction,
    CopyDependenciesAction,
    CopySourceAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability

from .actions import (
    NodejsNpmCIAction,
    NodejsNpmInstallAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmPackAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
)
from .npm import SubprocessNpm
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class NodejsNpmWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that knows how to pack
    NodeJS projects using NPM.
    """

    NAME = "NodejsNpmBuilder"

    CAPABILITY = Capability(language="nodejs", dependency_manager="npm", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    CONFIG_PROPERTY = "aws_sam"

    DEFAULT_BUILD_DIR = BuildDirectory.ARTIFACTS
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.NOT_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):
        super(NodejsNpmWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        if not osutils.file_exists(manifest_path):
            LOG.warning("package.json file not found. Continuing the build without dependencies.")
            self.actions = [CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES)]
            return

        subprocess_npm = SubprocessNpm(osutils)

        tar_dest_dir = osutils.joinpath(scratch_dir, "unpacked")
        tar_package_dir = osutils.joinpath(tar_dest_dir, "package")
        npm_pack = NodejsNpmPackAction(
            tar_dest_dir, scratch_dir, manifest_path, osutils=osutils, subprocess_npm=subprocess_npm
        )

        npm_copy_npmrc_and_lockfile = NodejsNpmrcAndLockfileCopyAction(tar_package_dir, source_dir, osutils=osutils)

        self.actions = [
            npm_pack,
            npm_copy_npmrc_and_lockfile,
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
        ]

        if self.download_dependencies:
            # install the dependencies into artifact folder
            self.actions.append(
                NodejsNpmWorkflow.get_install_action(source_dir, artifacts_dir, subprocess_npm, osutils, self.options)
            )

        artifacts_cleanup_actions = [
            NodejsNpmrcCleanUpAction(artifacts_dir, osutils=osutils),
            NodejsNpmLockFileCleanUpAction(artifacts_dir, osutils=osutils),
        ]

        # if no dependencies dir, just cleanup artifacts and we're done
        if not self.dependencies_dir:
            self.actions += artifacts_cleanup_actions
            return

        # if we downloaded dependencies, update dependencies_dir
        if self.download_dependencies:
            # clean up the dependencies folder first
            self.actions.append(CleanUpAction(self.dependencies_dir))
            # if combine_dependencies is set, we should keep dependencies and source code in the artifact folder
            # while copying the dependencies. Otherwise we should separate the dependencies and source code
            dependencies_dir_update_action = (
                CopyDependenciesAction if self.combine_dependencies else MoveDependenciesAction
            )
            self.actions.append(dependencies_dir_update_action(source_dir, artifacts_dir, self.dependencies_dir))
        # otherwise if we want to use the dependencies from dependencies_dir and we want to combine them,
        # then copy them into the artifacts dir
        elif self.combine_dependencies:
            self.actions.append(CopySourceAction(self.dependencies_dir, artifacts_dir))

        # cleanup
        self.actions += artifacts_cleanup_actions
        self.actions.append(NodejsNpmLockFileCleanUpAction(self.dependencies_dir, osutils=osutils))

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]

    @staticmethod
    def get_install_action(source_dir, install_dir, subprocess_npm, osutils, build_options):
        """
        Get the install action used to install dependencies at artifacts_dir

        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files

        :type install_dir: str
        :param install_dir: Dependencies will be installed in this directory.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper

        :type build_options: Dict
        :param build_options: Object containing build options configurations

        :type is_production: bool
        :param is_production: NPM installation mode is production (eg --production=false to force dev dependencies)

        :rtype: BaseAction
        :return: Install action to use
        """
        lockfile_path = osutils.joinpath(source_dir, "package-lock.json")
        shrinkwrap_path = osutils.joinpath(source_dir, "npm-shrinkwrap.json")

        npm_ci_option = False
        if build_options and isinstance(build_options, dict):
            npm_ci_option = build_options.get("use_npm_ci", False)

        if (osutils.file_exists(lockfile_path) or osutils.file_exists(shrinkwrap_path)) and npm_ci_option:
            return NodejsNpmCIAction(install_dir=install_dir, subprocess_npm=subprocess_npm)

        return NodejsNpmInstallAction(install_dir=install_dir, subprocess_npm=subprocess_npm)
