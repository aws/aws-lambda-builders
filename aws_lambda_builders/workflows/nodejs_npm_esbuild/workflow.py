"""
NodeJS NPM Workflow using the esbuild bundler
"""

import json
import logging
from pathlib import Path

from aws_lambda_builders.actions import (
    CleanUpAction,
    CopySourceAction,
    LinkSourceAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.utils import which
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability

from ...path_resolver import PathResolver
from ..nodejs_npm import NodejsNpmWorkflow
from ..nodejs_npm.npm import SubprocessNpm
from ..nodejs_npm.utils import OSUtils
from .actions import (
    EsbuildBundleAction,
)
from .esbuild import EsbuildExecutionError, SubprocessEsbuild

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
            if self.build_dir == self.source_dir
            else [CopySourceAction(source_dir=self.source_dir, dest_dir=self.build_dir, excludes=self.EXCLUDED_FILES)]
        )

        if self.download_dependencies:
            self.actions.append(
                NodejsNpmWorkflow.get_install_action(
                    source_dir=source_dir,
                    install_dir=self.build_dir,
                    subprocess_npm=self.subprocess_npm,
                    osutils=self.osutils,
                    build_options=self.options,
                    install_links=self.build_dir == self.source_dir,
                )
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
        if not self.dependencies_dir or self.build_dir == self.source_dir:
            self.actions.append(bundle_action)
            return

        if self.download_dependencies:
            # if we downloaded dependencies, bundle and update dependencies_dir
            self.actions += [
                bundle_action,
                CleanUpAction(self.dependencies_dir),
                MoveDependenciesAction(self.source_dir, self.scratch_dir, self.dependencies_dir),
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
        try:
            npm_bin_path_root = self.subprocess_npm.run(["root"], cwd=self.scratch_dir)
            npm_bin_path = str(Path(npm_bin_path_root, ".bin"))
        except FileNotFoundError:
            raise EsbuildExecutionError(message="The esbuild workflow couldn't find npm installed on your system.")
        executable_search_paths = [npm_bin_path]
        if self.executable_search_paths is not None:
            executable_search_paths = executable_search_paths + self.executable_search_paths
        return SubprocessEsbuild(self.osutils, executable_search_paths, which=which)
