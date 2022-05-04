"""
Commonly used utilities
"""

import os
import tarfile

from aws_lambda_builders.os_utils import OSUtils


class RubyOSUtils(OSUtils):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def get_bundle_dir(self, cwd):
        return os.path.join(cwd, ".bundle")
