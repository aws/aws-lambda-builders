"""
NodeJS NPM Workflow
"""

import logging

from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import (
    CopySourceAction,
    CleanUpAction,
    CopyDependenciesAction,
    MoveDependenciesAction,
)

from .actions import (
    NodejsNpmPackAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmInstallAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmCIAction,
)
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

    CONFIG_PROPERTY = "aws_sam"

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

        self.actions = self.actions_without_bundler(
            source_dir, artifacts_dir, scratch_dir, manifest_path, osutils, subprocess_npm
        )

    def actions_without_bundler(self, source_dir, artifacts_dir, scratch_dir, manifest_path, osutils, subprocess_npm):
        """
        Generate a list of Nodejs build actions without a bundler

        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files

        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.

        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type manifest_path: str
        :param manifest_path: path to package.json of an NPM project with the source to pack

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper

        :rtype: list
        :return: List of build actions to execute
        """
        tar_dest_dir = osutils.joinpath(scratch_dir, "unpacked")
        tar_package_dir = osutils.joinpath(tar_dest_dir, "package")
        npm_pack = NodejsNpmPackAction(
            tar_dest_dir, scratch_dir, manifest_path, osutils=osutils, subprocess_npm=subprocess_npm
        )

        npm_copy_npmrc_and_lockfile = NodejsNpmrcAndLockfileCopyAction(tar_package_dir, source_dir, osutils=osutils)

        actions = [
            npm_pack,
            npm_copy_npmrc_and_lockfile,
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
        ]

        if self.download_dependencies:
            # installed the dependencies into artifact folder
            install_action = NodejsNpmWorkflow.get_install_action(
                source_dir, artifacts_dir, subprocess_npm, osutils, self.options
            )
            actions.append(install_action)

            # if dependencies folder exists, copy or move dependencies from artifact folder to dependencies folder
            # depends on the combine_dependencies flag
            if self.dependencies_dir:
                # clean up the dependencies folder first
                actions.append(CleanUpAction(self.dependencies_dir))
                # if combine_dependencies is set, we should keep dependencies and source code in the artifact folder
                # while copying the dependencies. Otherwise we should separate the dependencies and source code
                if self.combine_dependencies:
                    actions.append(CopyDependenciesAction(source_dir, artifacts_dir, self.dependencies_dir))
                else:
                    actions.append(MoveDependenciesAction(source_dir, artifacts_dir, self.dependencies_dir))
        else:
            # if dependencies folder exists and not download dependencies, simply copy the dependencies from the
            # dependencies folder to artifact folder
            if self.dependencies_dir and self.combine_dependencies:
                actions.append(CopySourceAction(self.dependencies_dir, artifacts_dir))
            else:
                LOG.info(
                    "download_dependencies is False and dependencies_dir is None. Copying the source files into the "
                    "artifacts directory. "
                )

        actions.append(NodejsNpmrcCleanUpAction(artifacts_dir, osutils=osutils))
        actions.append(NodejsNpmLockFileCleanUpAction(artifacts_dir, osutils=osutils))

        if self.dependencies_dir:
            actions.append(NodejsNpmLockFileCleanUpAction(self.dependencies_dir, osutils=osutils))

        return actions

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]

    @staticmethod
    def get_install_action(source_dir, artifacts_dir, subprocess_npm, osutils, build_options, is_production=True):
        """
        Get the install action used to install dependencies at artifacts_dir

        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files

        :type artifacts_dir: str
        :param artifacts_dir: Dependencies will be installed in this directory.

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
            return NodejsNpmCIAction(artifacts_dir, subprocess_npm=subprocess_npm)

        return NodejsNpmInstallAction(artifacts_dir, subprocess_npm=subprocess_npm, is_production=is_production)
