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

    def __init__(self, source_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild):
        """
        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files


        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper
        """
        super(EsbuildBundleAction, self).__init__()
        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.bundler_config = bundler_config
        self.osutils = osutils
        self.subprocess_esbuild = subprocess_esbuild

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """

        if "entry_points" not in self.bundler_config:
            raise ActionFailedError("entry_points not set ({})".format(self.bundler_config))

        entry_points = self.bundler_config["entry_points"]

        if not isinstance(entry_points, list):
            raise ActionFailedError("entry_points must be a list ({})".format(self.bundler_config))

        if not entry_points:
            raise ActionFailedError("entry_points must not be empty ({})".format(self.bundler_config))

        entry_paths = [self.osutils.joinpath(self.source_dir, entry_point) for entry_point in entry_points]

        LOG.debug("NODEJS building %s using esbuild to %s", entry_paths, self.artifacts_dir)

        for entry_point in entry_paths:
            if not self.osutils.file_exists(entry_point):
                raise ActionFailedError("entry point {} does not exist".format(entry_point))

        args = entry_points + ["--bundle", "--platform=node", "--format=cjs"]
        minify = self.bundler_config.get("minify", True)
        sourcemap = self.bundler_config.get("sourcemap", True)
        target = self.bundler_config.get("target", "es2020")
        if minify:
            args.append("--minify")
        if sourcemap:
            args.append("--sourcemap")
        args.append("--target={}".format(target))
        args.append("--outdir={}".format(self.artifacts_dir))
        try:
            self.subprocess_esbuild.run(args, cwd=self.source_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))
