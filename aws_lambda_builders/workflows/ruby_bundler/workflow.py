"""
Ruby Bundler Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from .actions import RubyBundlerInstallAction, RubyBundlerVendorAction
from .utils import OSUtils
from .bundler import SubprocessBundler


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

        subprocess_bundler = SubprocessBundler(osutils)
        bundle_install = RubyBundlerInstallAction(artifacts_dir, subprocess_bundler=subprocess_bundler)

        bundle_deployment = RubyBundlerVendorAction(artifacts_dir, subprocess_bundler=subprocess_bundler)
        self.actions = [
            CopySourceAction(source_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
            bundle_install,
            bundle_deployment,
        ]
