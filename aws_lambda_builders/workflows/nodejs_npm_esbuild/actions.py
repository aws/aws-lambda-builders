"""
Actions specific to the esbuild bundler
"""
import logging

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildCommandBuilder
from aws_lambda_builders.workflows.nodejs_npm_esbuild.exceptions import EsbuildExecutionError

LOG = logging.getLogger(__name__)


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
        scratch_dir,
        artifacts_dir,
        bundler_config,
        osutils,
        subprocess_esbuild,
        manifest,
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

        :type subprocess_nodejs: aws_lambda_builders.workflows.nodejs_npm_esbuild.node.SubprocessNodejs
        :param subprocess_nodejs: An instance of the nodejs process wrapper

        :type skip_deps: bool
        :param skip_deps: if dependencies should be omitted from bundling
        """
        super(EsbuildBundleAction, self).__init__()
        self.scratch_dir = scratch_dir
        self.artifacts_dir = artifacts_dir
        self.bundler_config = bundler_config
        self.osutils = osutils
        self.subprocess_esbuild = subprocess_esbuild
        self.skip_deps = skip_deps
        self.manifest = manifest

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """
        esbuild_command_builder = EsbuildCommandBuilder(
            self.scratch_dir, self.artifacts_dir, self.bundler_config, self.osutils, self.manifest, self.skip_deps
        )
        esbuild_command_builder.set_and_validate_entry_points()
        args = esbuild_command_builder.get_esbuild_build_args()

        try:
            self.subprocess_esbuild.run(args, cwd=self.scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))


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
