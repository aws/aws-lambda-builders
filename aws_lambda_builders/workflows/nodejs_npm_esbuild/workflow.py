"""
NodeJS NPM Workflow using the esbuild bundler
"""

import logging
import json

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import (
    CopySourceAction,
    CleanUpAction,
    CopyDependenciesAction,
    MoveDependenciesAction,
)
from aws_lambda_builders.utils import which
from .actions import (
    EsbuildBundleAction,
    EsbuildCheckVersionAction,
    EsbuildMoveBundledArtifactsAction,
)
from .node import SubprocessNodejs
from .utils import is_experimental_esbuild_scope
from .esbuild import SubprocessEsbuild, EsbuildExecutionError
from ..nodejs_npm.actions import NodejsNpmCIAction, NodejsNpmInstallAction
from ..nodejs_npm.npm import SubprocessNpm
from ..nodejs_npm.utils import OSUtils
from ...path_resolver import PathResolver

LOG = logging.getLogger(__name__)


class NodejsNpmEsbuildWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that uses esbuild to bundle Node.js and transpile TS
    NodeJS projects using NPM with esbuild.
    """

    NAME = "NodejsNpmEsbuildBuilder"

    CAPABILITY = Capability(language="nodejs", dependency_manager="npm-esbuild", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    CONFIG_PROPERTY = "aws_sam"

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(NodejsNpmEsbuildWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        subprocess_npm = SubprocessNpm(osutils)
        subprocess_esbuild = self._get_esbuild_subprocess(subprocess_npm, scratch_dir, osutils)

        bundler_config = self.get_build_properties()

        if not osutils.file_exists(manifest_path):
            LOG.warning("package.json file not found. Bundling source without dependencies.")
            self.actions = [EsbuildBundleAction(source_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild)]
            return

        # if not is_experimental_esbuild_scope(self.experimental_flags):
        #     raise EsbuildExecutionError(message="Feature flag must be enabled to use this workflow")

        self.actions = self.actions_with_bundler(
            source_dir, scratch_dir, artifacts_dir, bundler_config, osutils, subprocess_npm, subprocess_esbuild
        )

    def actions_with_bundler(
        self, source_dir, scratch_dir, artifacts_dir, bundler_config, osutils, subprocess_npm, subprocess_esbuild
    ):
        """
        Generate a list of Nodejs build actions with a bundler

        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files

        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.

        :type bundler_config: dict
        :param bundler_config: configurations for the bundler action

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the esbuild process wrapper

        :rtype: list
        :return: List of build actions to execute
        """
        # pylint: disable=R0915
        lockfile_path = osutils.joinpath(source_dir, "package-lock.json")
        shrinkwrap_path = osutils.joinpath(source_dir, "npm-shrinkwrap.json")

        excluded = self.EXCLUDED_FILES + tuple("node_modules")
        actions = [CopySourceAction(source_dir, scratch_dir, excludes=excluded)]

        subprocess_node = SubprocessNodejs(osutils, self.executable_search_paths, which=which)

        if osutils.file_exists(lockfile_path) or osutils.file_exists(shrinkwrap_path):
            install_action = NodejsNpmCIAction(scratch_dir, subprocess_npm=subprocess_npm)
        else:
            install_action = NodejsNpmInstallAction(scratch_dir, subprocess_npm=subprocess_npm, is_production=False)

        if self.download_dependencies:
            actions.append(install_action)
            if self.dependencies_dir:
                actions.append(CleanUpAction(self.dependencies_dir))
                if self.combine_dependencies:
                    actions.append(CopyDependenciesAction(source_dir, artifacts_dir, self.dependencies_dir))
                    actions.append(
                        EsbuildBundleAction(scratch_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild)
                    )
                else:
                    # Bundle dependencies separately in a dependency layer. We need to check the esbuild
                    # version here to ensure that it supports skipping dependency bundling
                    actions.append(EsbuildCheckVersionAction(scratch_dir, subprocess_esbuild))
                    actions.append(
                        EsbuildBundleAction(
                            scratch_dir,
                            artifacts_dir,
                            bundler_config,
                            osutils,
                            subprocess_esbuild,
                            subprocess_node,
                            skip_deps=True,
                        )
                    )
                    actions.append(MoveDependenciesAction(source_dir, scratch_dir, self.dependencies_dir))
            else:
                # Standard build case
                actions.append(
                    EsbuildBundleAction(scratch_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild)
                )
        else:
            if self.dependencies_dir:
                if self.combine_dependencies:
                    actions.append(CopySourceAction(self.dependencies_dir, artifacts_dir))
                    actions.append(
                        EsbuildBundleAction(scratch_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild)
                    )
                else:
                    actions.append(EsbuildCheckVersionAction(scratch_dir, subprocess_esbuild))
                    actions.append(
                        EsbuildBundleAction(
                            scratch_dir,
                            artifacts_dir,
                            bundler_config,
                            osutils,
                            subprocess_esbuild,
                            subprocess_node,
                            skip_deps=True,
                        )
                    )
                    actions.append(CopySourceAction(scratch_dir, artifacts_dir, excludes=excluded))

        return actions

    def get_build_properties(self):
        """
        Get the aws_sam specific properties from the manifest, if they exist.

        :rtype: dict
        :return: Dict with aws_sam specific bundler configs
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

    def _get_esbuild_subprocess(self, subprocess_npm, scratch_dir, osutils) -> SubprocessEsbuild:
        npm_bin_path = subprocess_npm.run(["bin"], cwd=scratch_dir)
        executable_search_paths = [npm_bin_path]
        if self.executable_search_paths is not None:
            executable_search_paths = executable_search_paths + self.executable_search_paths
        return SubprocessEsbuild(osutils, executable_search_paths, which=which)
