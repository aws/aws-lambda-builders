"""
NodeJS NPM Workflow
"""

import logging
import json

from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.utils import which
from aws_lambda_builders.exceptions import WorkflowFailedError
from .actions import (
    NodejsNpmPackAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmInstallAction,
    NodejsNpmrcCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmCIAction,
    EsbuildBundleAction
)
from .utils import OSUtils
from .npm import SubprocessNpm
from .esbuild import SubprocessEsbuild

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

    def actions_without_bundler(self, source_dir, artifacts_dir, scratch_dir, manifest_path, osutils, subprocess_npm):
        tar_dest_dir = osutils.joinpath(scratch_dir, "unpacked")
        tar_package_dir = osutils.joinpath(tar_dest_dir, "package")
        npm_pack = NodejsNpmPackAction(
            tar_dest_dir, scratch_dir, manifest_path, osutils=osutils, subprocess_npm=subprocess_npm
        )
        npm_install = NodejsNpmInstallAction(artifacts_dir, subprocess_npm=subprocess_npm)
        npm_copy_npmrc = NodejsNpmrcCopyAction(tar_package_dir, source_dir, osutils=osutils)
        return [
            npm_pack,
            npm_copy_npmrc,
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
            npm_install,
            NodejsNpmrcCleanUpAction(artifacts_dir, osutils=osutils),
            NodejsNpmLockFileCleanUpAction(artifacts_dir, osutils=osutils),
        ]

    def actions_with_bundler(self, source_dir, artifacts_dir, bundler_config, osutils, subprocess_npm):
        lockfile_path = osutils.joinpath(source_dir, "package-lock.json")
        shrinkwrap_path = osutils.joinpath(source_dir, "npm-shrinkwrap.json")
        npm_bin_path = subprocess_npm.run(["bin"], cwd=source_dir)
        executable_search_paths = [npm_bin_path]
        if self.executable_search_paths is not None:
            executable_search_paths = executable_search_paths + self.executable_search_paths
        subprocess_esbuild = SubprocessEsbuild(osutils, executable_search_paths, which=which)

        if (osutils.file_exists(lockfile_path) or osutils.file_exists(shrinkwrap_path)):
            install_action = NodejsNpmCIAction(source_dir, subprocess_npm=subprocess_npm)
        else:
            install_action = NodejsNpmInstallAction(source_dir, subprocess_npm=subprocess_npm)

        esbuild_action = EsbuildBundleAction(source_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild)
        return [
            install_action,
            esbuild_action
        ]

    def get_manifest_config(self, osutils, manifest_path):
        LOG.debug("NODEJS reading manifest from %s", manifest_path)
        try:
            manifest = osutils.parse_json(manifest_path)
            if self.CONFIG_PROPERTY in manifest and isinstance(manifest[self.CONFIG_PROPERTY], dict):
                return manifest[self.CONFIG_PROPERTY]
            else:
                return {'bundler': ''}
        except (OSError, json.decoder.JSONDecodeError) as ex:
            raise WorkflowFailedError(workflow_name=self.NAME, action_name="ParseManifest", reason=str(ex))

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(NodejsNpmWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        subprocess_npm = SubprocessNpm(osutils)

        manifest_config = self.get_manifest_config(osutils, manifest_path)

        if manifest_config['bundler'] == 'esbuild':
            self.actions = self.actions_with_bundler(
                source_dir,
                artifacts_dir,
                manifest_config,
                osutils,
                subprocess_npm)
        else:
            self.actions = self.actions_without_bundler(
                source_dir,
                artifacts_dir,
                scratch_dir,
                manifest_path,
                osutils,
                subprocess_npm)

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [PathResolver(runtime=self.runtime, binary="npm")]
