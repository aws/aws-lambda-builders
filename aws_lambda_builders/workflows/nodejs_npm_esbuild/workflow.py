"""
NodeJS NPM Workflow using the esbuild bundler
"""

import json
import logging
import os
from pathlib import Path

from aws_lambda_builders.actions import (
    CleanUpAction,
    CopySourceAction,
    LinkSinglePathAction,
    LinkSourceAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.utils import which
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability
from aws_lambda_builders.workflows.nodejs_npm import NodejsNpmWorkflow
from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm.workflow import UNSUPPORTED_NPM_VERSION_MESSAGE
from aws_lambda_builders.workflows.nodejs_npm_esbuild.actions import (
    EsbuildBundleAction,
)
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildExecutionError, SubprocessEsbuild

LOG = logging.getLogger(__name__)


class NodejsNpmEsbuildWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that uses esbuild to bundle Node.js and transpile TS
    NodeJS projects using NPM with esbuild.
    """

    NAME = "NodejsNpmEsbuildBuilder"

    CAPABILITY = Capability(language="nodejs", dependency_manager="npm-esbuild", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git", "node_modules")

    CONFIG_PROPERTY = "aws_sam"

    DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.OPTIONALLY_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):
        super(NodejsNpmEsbuildWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        self.osutils = osutils or OSUtils()
        self.subprocess_npm = SubprocessNpm(self.osutils)
        self.subprocess_esbuild = self._get_esbuild_subprocess()
        self.manifest_dir = self.osutils.dirname(self.manifest_path)

        is_building_in_source = self.build_dir == self.source_dir
        is_external_manifest = self.manifest_dir != self.source_dir

        bundler_config = self.get_build_properties()

        if not self.osutils.file_exists(manifest_path):
            LOG.warning("package.json file not found. Bundling source without installing dependencies.")
            self.actions = [
                EsbuildBundleAction(
                    working_directory=self.source_dir,
                    output_directory=self.artifacts_dir,
                    bundler_config=bundler_config,
                    osutils=self.osutils,
                    subprocess_esbuild=self.subprocess_esbuild,
                    manifest=self.manifest_path,
                )
            ]
            return

        if not self.download_dependencies and not self.dependencies_dir:
            # Invalid workflow, can't have no dependency dir and no installation
            raise EsbuildExecutionError(
                message="Lambda Builders was unable to find the location of the dependencies since a "
                "dependencies directory was not provided and downloading dependencies is disabled."
            )

        # if we're building in the source directory, we don't have to copy the source code
        self.actions = (
            []
            if is_building_in_source
            else [CopySourceAction(source_dir=self.source_dir, dest_dir=self.build_dir, excludes=self.EXCLUDED_FILES)]
        )

        if is_external_manifest and not is_building_in_source:
            # copy the manifest file (package.json) to the build directory in case if the manifest file is not in the
            # same directory as the source code, and customer is not building in source.
            self.actions.append(
                CopySourceAction(source_dir=self.manifest_dir, dest_dir=self.build_dir, excludes=self.EXCLUDED_FILES)
            )

        if self.download_dependencies:
            if is_building_in_source and not NodejsNpmWorkflow.can_use_install_links(self.subprocess_npm):
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
                    subprocess_npm=self.subprocess_npm,
                    osutils=self.osutils,
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

        bundle_action = EsbuildBundleAction(
            working_directory=self.build_dir,
            output_directory=self.artifacts_dir,
            bundler_config=bundler_config,
            osutils=self.osutils,
            subprocess_esbuild=self.subprocess_esbuild,
            manifest=self.manifest_path,
            skip_deps=not self.combine_dependencies,
        )

        # If there's no dependencies_dir, just bundle and we're done.
        # Same thing if we're building in the source directory (since the dependencies persist in
        # the source directory, we don't want to move them or symlink them back to the source)
        if not self.dependencies_dir or is_building_in_source:
            self.actions.append(bundle_action)
            return

        if self.download_dependencies:
            # if we downloaded dependencies, bundle and update dependencies_dir
            self.actions += [
                bundle_action,
                CleanUpAction(self.dependencies_dir),
                MoveDependenciesAction(self.source_dir, self.scratch_dir, self.dependencies_dir, self.manifest_dir),
            ]
        else:
            # if we're reusing dependencies, then we need to symlink them before bundling
            self.actions += [
                LinkSourceAction(self.dependencies_dir, self.scratch_dir),
                bundle_action,
            ]

    def get_build_properties(self):
        """
        Get the aws_sam specific properties from the manifest, if they exist.

        Returns
        -------
        dict
            aws_sam specific bundler configs
        """
        if self.options and isinstance(self.options, dict):
            LOG.debug("Lambda Builders found the following esbuild properties:\n%s", json.dumps(self.options))
            return self.options
        return {}

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]

    def _get_esbuild_subprocess(self) -> SubprocessEsbuild:
        """
        Creates a subprocess object that is able to invoke the esbuild executable.

        Returns
        -------
        SubprocessEsbuild
            An esbuild specific subprocess object
        """
        try:
            npm_bin_path_root = self.subprocess_npm.run(["root"], cwd=self.build_dir)
            npm_bin_path = str(Path(npm_bin_path_root, ".bin"))
        except FileNotFoundError:
            raise EsbuildExecutionError(message="The esbuild workflow couldn't find npm installed on your system.")
        executable_search_paths = [npm_bin_path]
        if self.executable_search_paths is not None:
            executable_search_paths = executable_search_paths + self.executable_search_paths
        return SubprocessEsbuild(self.osutils, executable_search_paths, which=which)
