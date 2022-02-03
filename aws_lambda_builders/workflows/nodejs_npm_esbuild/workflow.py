"""
NodeJS NPM Workflow using the esbuild bundler
"""

import logging
import json

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import (
    CopySourceAction,
)
from aws_lambda_builders.utils import which
from aws_lambda_builders.exceptions import WorkflowFailedError
from .actions import (
    EsbuildBundleAction,
)
from .utils import is_experimental_esbuild_scope
from .esbuild import SubprocessEsbuild, EsbuildExecutionError
from ..nodejs_npm.actions import NodejsNpmCIAction, NodejsNpmInstallAction
from ..nodejs_npm.npm import SubprocessNpm
from ..nodejs_npm.utils import OSUtils
from ...path_resolver import PathResolver

LOG = logging.getLogger(__name__)


class NodejsNpmEsbuildWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that knows how to pack
    NodeJS projects using NPM.
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

        if not osutils.file_exists(manifest_path):
            LOG.warning("package.json file not found. Continuing the build without dependencies.")
            self.actions = [CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES)]
            return

        subprocess_npm = SubprocessNpm(osutils)

        manifest_config = self.get_manifest_config(osutils, manifest_path)

        if not is_experimental_esbuild_scope(self.experimental_flags):
            raise EsbuildExecutionError(message="Feature flag must be enabled to use this workflow")

        self.actions = self.actions_with_bundler(source_dir, artifacts_dir, manifest_config, osutils, subprocess_npm)

    def actions_with_bundler(self, source_dir, artifacts_dir, bundler_config, osutils, subprocess_npm):
        """
        Generate a list of Nodejs build actions with a bundler

        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files

        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.

        :type bundler_config: dict
        :param bundler_config: configurations for the bundler action

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper

        :rtype: list
        :return: List of build actions to execute
        """
        lockfile_path = osutils.joinpath(source_dir, "package-lock.json")
        shrinkwrap_path = osutils.joinpath(source_dir, "npm-shrinkwrap.json")
        npm_bin_path = subprocess_npm.run(["bin"], cwd=source_dir)
        executable_search_paths = [npm_bin_path]
        if self.executable_search_paths is not None:
            executable_search_paths = executable_search_paths + self.executable_search_paths
        subprocess_esbuild = SubprocessEsbuild(osutils, executable_search_paths, which=which)

        if osutils.file_exists(lockfile_path) or osutils.file_exists(shrinkwrap_path):
            install_action = NodejsNpmCIAction(source_dir, subprocess_npm=subprocess_npm)
        else:
            install_action = NodejsNpmInstallAction(source_dir, subprocess_npm=subprocess_npm, is_production=False)

        esbuild_action = EsbuildBundleAction(source_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild)
        return [install_action, esbuild_action]

    def get_manifest_config(self, osutils, manifest_path):
        """
        Get the aws_sam specific properties from the manifest, if they exist.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type manifest_path: str
        :param manifest_path: Path to the manifest file

        :rtype: dict
        :return: Dict with aws_sam specific bundler configs
        """
        LOG.debug("NODEJS reading manifest from %s", manifest_path)
        try:
            manifest = osutils.parse_json(manifest_path)
            if self.CONFIG_PROPERTY in manifest and isinstance(manifest[self.CONFIG_PROPERTY], dict):
                return manifest[self.CONFIG_PROPERTY]
            else:
                return {"bundler": ""}
        except (OSError, json.decoder.JSONDecodeError) as ex:
            raise WorkflowFailedError(workflow_name=self.NAME, action_name="ParseManifest", reason=str(ex))

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]
