"""
Action to build a specific Makefile target
"""

import logging
from pathlib import Path

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .make import MakeExecutionError

LOG = logging.getLogger(__name__)


class ProvidedMakeAction(BaseAction):

    """
    A Lambda Builder Action that builds and packages a provided runtime project using Make.
    """

    NAME = "MakeBuild"
    DESCRIPTION = "Running build target on Makefile"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, artifacts_dir, scratch_dir, manifest_path, osutils, subprocess_make, build_logical_id):
        """
        :type artifacts_dir: str
        :param artifacts_dir: directory where artifacts needs to be stored.

        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type manifest_path: str
        :param manifest_path: path to Makefile of an Make project with the source in same folder.

        :type osutils: aws_lambda_builders.workflows.provided_make.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_make aws_lambda_builders.workflows.provided_make.make.SubprocessMake
        :param subprocess_make: An instance of the Make process wrapper
        """
        super(ProvidedMakeAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.scratch_dir = scratch_dir
        self.manifest_path = manifest_path
        self.osutils = osutils
        self.subprocess_make = subprocess_make
        self.build_logical_id = build_logical_id

    def _artifact_dir_path(self):
        # This is required when running on windows to determine if we are running in linux
        # subsystem or on native cmd or powershell.
        return Path(self.artifacts_dir).as_posix() if self.osutils.which("sh") else self.artifacts_dir

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when Make Build fails.
        """

        # Create the Artifacts Directory if it doesnt exist.
        if not self.osutils.exists(self.artifacts_dir):
            self.osutils.makedirs(self.artifacts_dir)

        try:
            current_env = self.osutils.environ().copy()
            artifacts_dir = self._artifact_dir_path()
            LOG.info("Current Artifacts Directory : %s", artifacts_dir)
            current_env.update({"ARTIFACTS_DIR": artifacts_dir})
            # Export environmental variables that might be needed by other binaries used
            # within the Makefile.
            self.subprocess_make.run(
                ["build-{logical_id}".format(logical_id=self.build_logical_id)], env=current_env, cwd=self.scratch_dir,
            )
        except MakeExecutionError as ex:
            raise ActionFailedError(str(ex))
