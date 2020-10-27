"""
Actions for Ruby dependency resolution with Bundler
"""

import logging

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .bundler import BundlerExecutionError

LOG = logging.getLogger(__name__)


class RubyBundlerInstallAction(BaseAction):

    """
    A Lambda Builder Action which runs bundle install in order to build a full Gemfile.lock
    """

    NAME = "RubyBundle"
    DESCRIPTION = "Resolving dependencies using Bundler"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, source_dir, subprocess_bundler):
        super(RubyBundlerInstallAction, self).__init__()
        self.source_dir = source_dir
        self.subprocess_bundler = subprocess_bundler

    def execute(self):
        try:
            LOG.debug("Running bundle install in %s", self.source_dir)
            self.subprocess_bundler.run(["install", "--without", "development", "test"], cwd=self.source_dir)
        except BundlerExecutionError as ex:
            raise ActionFailedError(str(ex))


class RubyBundlerVendorAction(BaseAction):
    """
    A Lambda Builder Action which vendors dependencies to the vendor/bundle directory.
    """

    NAME = "RubyBundleDeployment"
    DESCRIPTION = "Package dependencies for deployment."
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, source_dir, subprocess_bundler):
        super(RubyBundlerVendorAction, self).__init__()
        self.source_dir = source_dir
        self.subprocess_bundler = subprocess_bundler

    def execute(self):
        try:
            LOG.debug("Running bundle install --deployment in %s", self.source_dir)
            self.subprocess_bundler.run(
                ["install", "--deployment", "--without", "development", "test"], cwd=self.source_dir
            )
        except BundlerExecutionError as ex:
            raise ActionFailedError(str(ex))
