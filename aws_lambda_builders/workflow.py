"""
Implementation of a base workflow
"""

import os
import logging
import six

from aws_lambda_builders.registry import WorkflowMetaClass

LOG = logging.getLogger(__name__)


class BaseWorkflow(six.with_metaclass(WorkflowMetaClass, object)):
    """
    Default implementation of the builder workflow. It provides several useful capabilities out-of-box that help
    minimize the scope of build actions.
    """

    # Capabilities supported by this builder. Must be an instance of `BuilderCapability` named tuple
    CAPABILITY = None

    SUPPORTED_MANIFESTS = []
    NAME = 'BaseBuilder'

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 manifest_path,
                 runtime=None,
                 optimizations=None,
                 options=None):
        """
        Initialize the builder with given arguments. These arguments together form the "public API" that each
        build action must support at the minimum.

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type artifacts_dir: str
        :param artifacts_dir:
            Path to a folder where the built artifacts should be placed

        :type manifest_path: str
        :param manifest_path:
            Path to the dependency manifest

        :type runtime: str
        :param runtime:
            Optional, name of the AWS Lambda runtime that you are building for. This is sent to the builder for
            informational purposes.

        :type optimizations: dict
        :param optimizations:
            Optional dictionary of optimization flags to pass to the build action. **Not supported**.

        :type options: dict
        :param options:
            Optional dictionary of options ot pass to build action. **Not supported**.
        """

        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.optimizations = optimizations
        self.options = options

        # Actions are registered by the subclasses as they seem fit
        self.actions = []

    def is_supported(self):
        """
        Is the given manifest supported?
        """

        return os.path.basename(self.manifest_path) in self.SUPPORTED_MANIFESTS

    def run(self):
        """
        Actually perform the build by executing registered actions

        :return:
        """
        pass
