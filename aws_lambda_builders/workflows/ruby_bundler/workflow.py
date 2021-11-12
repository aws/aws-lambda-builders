"""
Ruby Bundler Workflow
"""
import logging

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction, CopyDependenciesAction, CleanUpAction
from .actions import RubyBundlerInstallAction, RubyBundlerVendorAction
from .utils import OSUtils
from .bundler import SubprocessBundler

LOG = logging.getLogger(__name__)


class RubyBundlerWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that knows how to build
    Ruby projects using Bundler.
    """

    NAME = "RubyBundlerBuilder"

    CAPABILITY = Capability(language="ruby", dependency_manager="bundler", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(RubyBundlerWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        if osutils is None:
            osutils = OSUtils()

        self.actions = [CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES)]

        if self.download_dependencies:
            # installed the dependencies into artifact folder
            subprocess_bundler = SubprocessBundler(osutils)
            bundle_install = RubyBundlerInstallAction(artifacts_dir, subprocess_bundler=subprocess_bundler)
            bundle_deployment = RubyBundlerVendorAction(artifacts_dir, subprocess_bundler=subprocess_bundler)
            self.actions.append(bundle_install)
            self.actions.append(bundle_deployment)

            # if dependencies folder exists, copy dependencies into dependencies into dependencies folder
            if self.dependencies_dir:
                # clean up the dependencies first
                self.actions.append(CleanUpAction(self.dependencies_dir))
                self.actions.append(CopyDependenciesAction(source_dir, artifacts_dir, self.dependencies_dir))
        else:
            # if dependencies folder exists and not download dependencies, simply copy the dependencies from the
            # dependencies folder to artifact folder
            if self.dependencies_dir:
                self.actions.append(CopySourceAction(self.dependencies_dir, artifacts_dir))
            else:
                LOG.info(
                    "download_dependencies is False and dependencies_dir is None. Copying the source files into the "
                    "artifacts directory. "
                )
