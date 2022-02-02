"""
Actions specific to the esbuild bundler
"""
import logging
from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .esbuild import EsbuildExecutionError

LOG = logging.getLogger(__name__)


class EsbuildBundleAction(BaseAction):

    """
    A Lambda Builder Action that packages a Node.js package using esbuild into a single file
    optionally transpiling TypeScript
    """

    NAME = "EsbuildBundle"
    DESCRIPTION = "Packaging source using Esbuild"
    PURPOSE = Purpose.COPY_SOURCE

    ENTRY_POINTS = "EntryPoints"

    def __init__(self, scratch_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild):
        """
        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper
        """
        super(EsbuildBundleAction, self).__init__()
        self.scratch_dir = scratch_dir
        self.artifacts_dir = artifacts_dir
        self.bundler_config = bundler_config
        self.osutils = osutils
        self.subprocess_esbuild = subprocess_esbuild

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """

        if self.ENTRY_POINTS not in self.bundler_config:
            raise ActionFailedError(f"{self.ENTRY_POINTS} not set ({self.bundler_config})")

        entry_points = self.bundler_config[self.ENTRY_POINTS]

        if not isinstance(entry_points, list):
            raise ActionFailedError(f"{self.ENTRY_POINTS} must be a list ({self.bundler_config})")

        if not entry_points:
            raise ActionFailedError(f"{self.ENTRY_POINTS} must not be empty ({self.bundler_config})")

        entry_paths = [self.osutils.joinpath(self.scratch_dir, entry_point) for entry_point in entry_points]

        LOG.debug("NODEJS building %s using esbuild to %s", entry_paths, self.artifacts_dir)

        for entry_point in entry_paths:
            if not self.osutils.file_exists(entry_point):
                raise ActionFailedError("entry point {} does not exist".format(entry_point))

        args = entry_points + ["--bundle", "--platform=node", "--format=cjs"]
        minify = self.bundler_config.get("Minify", True)
        sourcemap = self.bundler_config.get("SourceMap", True)
        target = self.bundler_config.get("Target", "es2020")
        if minify:
            args.append("--minify")
        if sourcemap:
            args.append("--sourcemap")
        args.append("--target={}".format(target))
        args.append("--outdir={}".format(self.artifacts_dir))
        try:
            self.subprocess_esbuild.run(args, cwd=self.scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))
