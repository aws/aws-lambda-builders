"""
Actions specific to the esbuild bundler
"""
import logging
from typing import Any, Dict

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import EsbuildCommandBuilder, SubprocessEsbuild
from aws_lambda_builders.workflows.nodejs_npm_esbuild.exceptions import EsbuildExecutionError

LOG = logging.getLogger(__name__)

EXTERNAL_KEY = "external"
# minimum esbuild version required to use "--external"
MINIMUM_VERSION_FOR_EXTERNAL = "0.14.13"


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
        working_directory: str,
        output_directory: str,
        bundler_config: Dict[str, Any],
        osutils: OSUtils,
        subprocess_esbuild: SubprocessEsbuild,
        manifest: str,
        skip_deps=False,
    ):
        """
        Parameters
        ----------
        working_directory : str
            directory where esbuild is executed
        output_directory : str
            an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.
        bundler_config : Dict[str, Any]
            the bundle configuration
        osutils : OSUtils
            An instance of OS Utilities for file manipulation
        subprocess_esbuild : SubprocessEsbuild
            An instance of the Esbuild process wrapper
        manifest : str
            path to package.json file contents to read
        skip_deps : bool, optional
            if dependencies should be omitted from bundling, by default False
        """
        super(EsbuildBundleAction, self).__init__()
        self._working_directory = working_directory
        self._output_directory = output_directory
        self._bundler_config = bundler_config
        self._osutils = osutils
        self._subprocess_esbuild = subprocess_esbuild
        self._skip_deps = skip_deps
        self._manifest = manifest

    def execute(self) -> None:
        """
        Runs the action.

        Raises
        ------
        ActionFailedError
            when esbuild packaging fails
        """
        esbuild_command = EsbuildCommandBuilder(
            self._working_directory, self._output_directory, self._bundler_config, self._osutils, self._manifest
        )

        if self._should_bundle_deps_externally():
            check_minimum_esbuild_version(
                minimum_version_required=MINIMUM_VERSION_FOR_EXTERNAL,
                working_directory=self._working_directory,
                subprocess_esbuild=self._subprocess_esbuild,
            )
            esbuild_command.build_with_no_dependencies()
            if EXTERNAL_KEY in self._bundler_config:
                # Already marking everything as external,
                # shouldn't attempt to do it again when building args from config
                self._bundler_config.pop(EXTERNAL_KEY)

        args = (
            esbuild_command.build_entry_points().build_default_values().build_esbuild_args_from_config().get_command()
        )

        try:
            self._subprocess_esbuild.run(args, cwd=self._working_directory)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))

    def _should_bundle_deps_externally(self) -> bool:
        """
        Checks if all dependencies should be marked as external and not bundled with source code

        :rtype: boolean
        :return: True if all dependencies should be marked as external
        """
        return self._skip_deps or "./node_modules/*" in self._bundler_config.get(EXTERNAL_KEY, [])


def check_minimum_esbuild_version(
    minimum_version_required: str, working_directory: str, subprocess_esbuild: SubprocessEsbuild
):
    """
    Checks esbuild version against a minimum version required.

    Parameters
    ----------
    minimum_version_required: str
        minimum esbuild version required for check to pass

    working_directory: str
        directory where esbuild is executed

    subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild
        An instance of the Esbuild process wrapper

    Raises
    ----------
    lambda_builders.actions.ActionFailedError
        when esbuild version checking fails
    """
    args = ["--version"]

    try:
        version = subprocess_esbuild.run(args, cwd=working_directory)
    except EsbuildExecutionError as ex:
        raise ActionFailedError(str(ex))

    LOG.debug("Found esbuild with version: %s", version)

    try:
        check_version = _get_version_tuple(minimum_version_required)
        esbuild_version = _get_version_tuple(version)

        if esbuild_version < check_version:
            raise ActionFailedError(
                f"Unsupported esbuild version. To use a dependency layer, the esbuild version must be at "
                f"least {minimum_version_required}. Version found: {version}"
            )
    except (TypeError, ValueError) as ex:
        raise ActionFailedError(f"Unable to parse esbuild version: {str(ex)}")


def _get_version_tuple(version_string: str):
    """
    Get an integer tuple representation of the version for comparison

    Parameters
    ----------
    version_string: str
        string containing the esbuild version

    Returns
    ----------
    tuple
        version tuple used for comparison
    """
    return tuple(map(int, version_string.split(".")))
