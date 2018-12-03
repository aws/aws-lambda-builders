"""
Action to resolve NodeJS dependencies using NPM
"""

import logging
from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .utils import OSUtils
from .npm import SubprocessNpm, NpmError

LOG = logging.getLogger(__name__)


class NodejsNpmPackAction(BaseAction):

    NAME = 'CopySource'
    DESCRIPTION = "Packaging source using NPM"
    PURPOSE = Purpose.COPY_SOURCE

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
            package_path = "file:{}".format(self.osutils.abspath(self.osutils.dirname(self.manifest_path)))

            LOG.debug("NODEJS packaging %s to %s", package_path, self.scratch_dir)

            tarfile_name = self.subprocess_npm.main(['pack', '-q', package_path], cwd=self.scratch_dir)

            LOG.debug("NODEJS packed to %s", tarfile_name)

            tarfile_path = self.osutils.joinpath(self.scratch_dir, tarfile_name)

            self.osutils.extract_tarfile(tarfile_path, tarfile_path + '-unpacked')

            self.osutils.copytree(self.osutils.joinpath(tarfile_path + '-unpacked', 'package'), self.artifacts_dir)

        except NpmError as ex:
            raise ActionFailedError(str(ex))


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
            LOG.debug("NODEJS installing in: %s from: %s", self.artifacts_dir, self.manifest_path)

            self.subprocess_npm.main(
                    ['install', '-q', '--no-audit', '--no-save', '--production'],
                    cwd=self.artifacts_dir
            )

        except NpmError as ex:
            raise ActionFailedError(str(ex))
