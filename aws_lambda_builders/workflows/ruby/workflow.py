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

    CAPABILITY = Capability(language="ruby",
                            dependency_manager="bundler",
                            application_framework=None)

    EXCLUDED_FILES = (".aws-sam")

    def __init__(self,
                 source_dir,
                 runtime=None,
                 osutils=None,
                 **kwargs):

        super(RubyBundlerWorkflow, self).__init__(source_dir,
                                                  artifacts_dir=None,
                                                  scratch_dir=None,
                                                  manifest_path=None,
                                                  runtime=runtime,
                                                  **kwargs)

        if osutils is None:
            osutils = OSUtils()

        subprocess_bundler = SubprocessBundler(osutils)

        tar_dest_dir = osutils.joinpath(scratch_dir, 'unpacked')
        tar_package_dir = osutils.joinpath(tar_dest_dir, 'package')

        bundle_install = RubyBundlerInstallAction(source_dir,
                                                  osutils=osutils,
                                                  subprocess_bundler=subprocess_bundler)

        bundle_deployment = RubyBundlerVendorAction(source_dir,
                                                    osutils=osutils,
                                                    subprocess_bundler=subprocess_bundler)
        self.actions = [
            CopySourceAction(tar_package_dir, artifacts_dir, excludes=self.EXCLUDED_FILES),
            bundle_install,
            bundle_deployment,
        ]
