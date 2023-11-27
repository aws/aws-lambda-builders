"""
NodeJS NPM Workflow
"""

import logging
import os
from typing import Optional

from aws_lambda_builders.actions import (
    CleanUpAction,
    CopyDependenciesAction,
    CopySourceAction,
    LinkSinglePathAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmCIAction,
    NodejsNpmInstallAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmPackAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmUpdateAction,
)
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils

LOG = logging.getLogger(__name__)

# npm>=8.8.0 supports --install-links
MINIMUM_NPM_VERSION_INSTALL_LINKS = (8, 8)
UNSUPPORTED_NPM_VERSION_MESSAGE = (
    "Building in source was enabled, however the "
    "currently installed npm version does not support "
    "--install-links. Please ensure that the npm "
    "version is at least 8.8.0. Switching to build "
    f"in outside of the source directory.{os.linesep}"
    "https://docs.npmjs.com/cli/v8/using-npm/changelog#v880-2022-04-27"
)


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
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):
        super(NodejsNpmWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()
        self.osutils = osutils

        if not osutils.file_exists(manifest_path):
            LOG.warning("package.json file not found. Continuing the build without dependencies.")
            self.actions = [CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES)]
            return

        subprocess_npm = SubprocessNpm(osutils)

        tar_dest_dir = osutils.joinpath(scratch_dir, "unpacked")
        tar_package_dir = osutils.joinpath(tar_dest_dir, "package")
        # TODO: we should probably unpack straight into artifacts dir, rather than unpacking into tar_dest_dir and
        # then copying into artifacts. Just make sure EXCLUDED_FILES are not included, or remove them.
        npm_pack = NodejsNpmPackAction(
            tar_dest_dir, scratch_dir, manifest_path, osutils=osutils, subprocess_npm=subprocess_npm
        )

        npm_copy_npmrc_and_lockfile = NodejsNpmrcAndLockfileCopyAction(tar_package_dir, source_dir, osutils=osutils)

        self.manifest_dir = self.osutils.dirname(self.manifest_path)
        is_building_in_source = self.build_dir == self.source_dir
        is_external_manifest = self.manifest_dir != self.source_dir
        self.actions = [
            npm_pack,
            npm_copy_npmrc_and_lockfile,
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
        ]

        if is_external_manifest:
            # npm pack only copies source code if the manifest is in the same directory as the source code, we need to
            # copy the source code if the customer specified a different manifest path
            self.actions.append(CopySourceAction(self.source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES))

        if self.download_dependencies:
            if is_building_in_source and not self.can_use_install_links(subprocess_npm):
                LOG.warning(UNSUPPORTED_NPM_VERSION_MESSAGE)

                is_building_in_source = False
                self.build_dir = self._select_build_dir(build_in_source=False)

            self.actions.append(
                NodejsNpmWorkflow.get_install_action(
                    source_dir=source_dir,
                    # run npm install in the directory where the manifest (package.json) exists if customer is building
                    # in source, and manifest directory is different from source.
                    # This will let NPM find the local dependencies that are defined in the manifest file (they are
                    # usually defined as relative to the manifest location, and that is why we run `npm install` in the
                    # manifest directory instead of source directory).
                    # If customer is not building in source, so it is ok to run `npm install` in the build
                    # directory (the artifacts directory in this case), as the local dependencies are not supported.
                    install_dir=self.manifest_dir if is_building_in_source and is_external_manifest else self.build_dir,
                    subprocess_npm=subprocess_npm,
                    osutils=osutils,
                    build_options=self.options,
                    is_building_in_source=is_building_in_source,
                )
            )

            if is_building_in_source and is_external_manifest:
                # Since we run `npm install` in the manifest directory, so we need to link the node_modules directory in
                # the source directory.
                source_dependencies_path = os.path.join(self.source_dir, "node_modules")
                manifest_dependencies_path = os.path.join(self.manifest_dir, "node_modules")
                self.actions.append(
                    LinkSinglePathAction(source=manifest_dependencies_path, dest=source_dependencies_path)
                )

        if self.download_dependencies and is_building_in_source:
            self.actions += self._actions_for_linking_source_dependencies_to_artifacts

        # if no dependencies dir, just cleanup artifacts and we're done
        if not self.dependencies_dir:
            self.actions += self._actions_for_cleanup
            return

        # if we downloaded dependencies, update dependencies_dir
        if self.download_dependencies:
            self.actions += self._actions_for_updating_dependencies_dir
        # otherwise if we want to use the dependencies from dependencies_dir and we want to combine them,
        # then copy them into the artifacts dir
        elif self.combine_dependencies:
            self.actions.append(
                CopySourceAction(self.dependencies_dir, artifacts_dir, maintain_symlinks=is_building_in_source)
            )

        self.actions += self._actions_for_cleanup

    @property
    def _actions_for_cleanup(self):
        actions = [NodejsNpmrcCleanUpAction(self.artifacts_dir, osutils=self.osutils)]

        # we don't want to cleanup the lockfile in the source code's symlinked node_modules
        if self.build_dir != self.source_dir:
            actions.append(NodejsNpmLockFileCleanUpAction(self.artifacts_dir, osutils=self.osutils))
        if self.build_dir != self.source_dir and self.dependencies_dir:
            actions.append(NodejsNpmLockFileCleanUpAction(self.dependencies_dir, osutils=self.osutils))

        return actions

    @property
    def _actions_for_linking_source_dependencies_to_artifacts(self):
        source_dependencies_path = os.path.join(self.source_dir, "node_modules")
        artifact_dependencies_path = os.path.join(self.artifacts_dir, "node_modules")
        return [LinkSinglePathAction(source=source_dependencies_path, dest=artifact_dependencies_path)]

    @property
    def _actions_for_updating_dependencies_dir(self):
        # clean up the dependencies folder first
        actions = [CleanUpAction(self.dependencies_dir)]
        # if combine_dependencies is set, we should keep dependencies and source code in the artifact folder
        # while copying the dependencies. Otherwise we should separate the dependencies and source code
        if self.combine_dependencies:
            actions.append(
                CopyDependenciesAction(
                    source_dir=self.source_dir,
                    artifact_dir=self.artifacts_dir,
                    destination_dir=self.dependencies_dir,
                    maintain_symlinks=self.build_dir == self.source_dir,
                    manifest_dir=self.manifest_dir,
                )
            )
        else:
            actions.append(
                MoveDependenciesAction(
                    source_dir=self.source_dir,
                    artifact_dir=self.artifacts_dir,
                    destination_dir=self.dependencies_dir,
                    manifest_dir=self.manifest_dir,
                )
            )

        return actions

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]

    @staticmethod
    def get_install_action(
        source_dir: str,
        install_dir: str,
        subprocess_npm: SubprocessNpm,
        osutils: OSUtils,
        build_options: Optional[dict],
        is_building_in_source: Optional[bool] = False,
    ):
        """
        Get the install action used to install dependencies.

        Parameters
        ----------
        source_dir : str
            an existing (readable) directory containing source files
        install_dir : str
            Dependencies will be installed in this directory
        subprocess_npm : SubprocessNpm
            An instance of the NPM process wrapper
        osutils : OSUtils
            An instance of OS Utilities for file manipulation
        build_options : Optional[dict]
            Object containing build options configurations
        is_building_in_source : Optional[bool]
            States whether --build-in-source flag is set or not

        Returns
        -------
        BaseAction
            Install action to use
        """
        lockfile_path = osutils.joinpath(source_dir, "package-lock.json")
        shrinkwrap_path = osutils.joinpath(source_dir, "npm-shrinkwrap.json")

        npm_ci_option = False
        if build_options and isinstance(build_options, dict):
            npm_ci_option = build_options.get("use_npm_ci", False)

        if (osutils.file_exists(lockfile_path) or osutils.file_exists(shrinkwrap_path)) and npm_ci_option:
            return NodejsNpmCIAction(
                install_dir=install_dir, subprocess_npm=subprocess_npm, install_links=is_building_in_source
            )

        if is_building_in_source:
            return NodejsNpmUpdateAction(install_dir=install_dir, subprocess_npm=subprocess_npm)

        return NodejsNpmInstallAction(install_dir=install_dir, subprocess_npm=subprocess_npm)

    @staticmethod
    def can_use_install_links(npm_process: SubprocessNpm) -> bool:
        """
        Checks the version of npm that is currently installed to determine
        whether or not --install-links can be used

        Parameters
        ----------
        npm_process: SubprocessNpm
            Object containing helper methods to call the npm process

        Returns
        -------
        bool
            True if the current npm version meets the minimum for --install-links
        """
        try:
            current_version = npm_process.run(["--version"])

            LOG.debug(f"Currently installed version of npm is: {current_version}")

            current_version = current_version.split(".")

            major_version = int(current_version[0])
            minor_version = int(current_version[1])
        except (ValueError, IndexError):
            LOG.debug(f"Failed to parse {current_version} output from npm for --install-links validation")
            return False

        is_older_major_version = major_version < MINIMUM_NPM_VERSION_INSTALL_LINKS[0]
        is_older_patch_version = (
            major_version == MINIMUM_NPM_VERSION_INSTALL_LINKS[0]
            and minor_version < MINIMUM_NPM_VERSION_INSTALL_LINKS[1]
        )

        return not (is_older_major_version or is_older_patch_version)
