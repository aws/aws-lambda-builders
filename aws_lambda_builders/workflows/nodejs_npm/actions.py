"""
Action to resolve NodeJS dependencies using NPM
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from aws_lambda_builders.workflows.python_pip.utils import OSUtils
from .npm import SubprocessNpm, NpmError

import logging

LOG = logging.getLogger(__name__)


class NodejsNpmInstallAction(BaseAction):

    NAME = 'ResolveDependencies'
    DESCRIPTION = "Installing dependencies from NPM"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, scratch_dir, manifest_path, runtime, osutils=None, subprocess_npm=None):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.runtime = runtime

        self.osutils = osutils
        if osutils is None:
            self.osutils = OSUtils()

        self.subprocess_npm = subprocess_npm

        if self.subprocess_npm is None:
            self.subprocess_npm = SubprocessNpm(self.osutils)

    def execute(self):
        try:
            LOG.debug("NODEJS building in: %s from: %s", self.artifacts_dir, self.manifest_path)

            if not self.osutils.file_exists(self.osutils.joinpath(self.artifacts_dir, 'package.json')):
                raise ActionFailedError('package.json not found in: %s' % self.artifacts_dir)

            self.subprocess_npm.main(['install', '--production'], cwd=self.artifacts_dir)

        except NpmError as ex:
            raise ActionFailedError(str(ex))
