"""
Actions specific to the esbuild bundler
"""
import logging
from typing import Any, Dict

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildCommandBuilder, SubprocessEsbuild
from aws_lambda_builders.workflows.nodejs_npm_esbuild.exceptions import EsbuildExecutionError

LOG = logging.getLogger(__name__)

EXTERNAL_KEY = "external"


class EsbuildBundleAction(BaseAction):

    """
    A Lambda Builder Action that packages a Node.js package using esbuild into a single file
    optionally transpiling TypeScript
    """

    NAME = "EsbuildBundle"
    DESCRIPTION = "Packaging source using Esbuild"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(
        self,
        scratch_dir: str,
        artifacts_dir: str,
        bundler_config: Dict[str, Any],
        osutils: OSUtils,
        subprocess_esbuild: SubprocessEsbuild,
        manifest: str,
        skip_deps=False,
    ):
        """
        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper

        :type skip_deps: bool
        :param skip_deps: if dependencies should be omitted from bundling

        :type bundler_config: Dict[str,Any]
        :param bundler_config: the bundler configuration

        :type manifest: str
        :param manifest: path to package.json file contents to read
        """
        super(EsbuildBundleAction, self).__init__()
        self._scratch_dir = scratch_dir
        self._artifacts_dir = artifacts_dir
        self._bundler_config = bundler_config
        self._osutils = osutils
        self._subprocess_esbuild = subprocess_esbuild
        self._skip_deps = skip_deps
        self._manifest = manifest

    def execute(self) -> None:
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """
        esbuild_command = EsbuildCommandBuilder(
            self._scratch_dir, self._artifacts_dir, self._bundler_config, self._osutils, self._manifest
        )

        if self._should_bundle_deps_externally():
            esbuild_command.build_with_no_dependencies()
            if EXTERNAL_KEY in self._bundler_config:
                # Already marking everything as external,
                # shouldn't attempt to do it again when building args from config
                self._bundler_config.pop(EXTERNAL_KEY)

        args = (
            esbuild_command.build_entry_points().build_default_values().build_esbuild_args_from_config().get_command()
        )

        try:
            self._subprocess_esbuild.run(args, cwd=self._scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))

    def _should_bundle_deps_externally(self) -> bool:
        """
        Checks if all dependencies should be marked as external and not bundled with source code

        :rtype: boolean
        :return: True if all dependencies should be marked as external
        """
        return self._skip_deps or "./node_modules/*" in self._bundler_config.get(EXTERNAL_KEY, [])


class EsbuildCheckVersionAction(BaseAction):
    """
    A Lambda Builder Action that verifies that esbuild is a version supported by sam accelerate
    """

    NAME = "EsbuildCheckVersion"
    DESCRIPTION = "Checking esbuild version"
    PURPOSE = Purpose.COMPILE_SOURCE

    MIN_VERSION = "0.14.13"

    def __init__(self, scratch_dir, subprocess_esbuild):
        """
        :type scratch_dir: str
        :param scratch_dir: temporary directory where esbuild is executed

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper
        """
        super().__init__()
        self.scratch_dir = scratch_dir
        self.subprocess_esbuild = subprocess_esbuild

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild version checking fails
        """
        args = ["--version"]

        try:
            version = self.subprocess_esbuild.run(args, cwd=self.scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))

        LOG.debug("Found esbuild with version: %s", version)

        try:
            check_version = EsbuildCheckVersionAction._get_version_tuple(self.MIN_VERSION)
            esbuild_version = EsbuildCheckVersionAction._get_version_tuple(version)

            if esbuild_version < check_version:
                raise ActionFailedError(
                    f"Unsupported esbuild version. To use a dependency layer, the esbuild version must be at "
                    f"least {self.MIN_VERSION}. Version found: {version}"
                )
        except (TypeError, ValueError) as ex:
            raise ActionFailedError(f"Unable to parse esbuild version: {str(ex)}")

    @staticmethod
    def _get_version_tuple(version_string):
        """
        Get an integer tuple representation of the version for comparison

        :type version_string: str
        :param version_string: string containing the esbuild version

        :rtype: tuple
        :return: version tuple used for comparison
        """
        return tuple(map(int, version_string.split(".")))
