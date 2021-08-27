"""
Common Actions for the Java Workflows
"""

import os
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose


class JavaCopyDependenciesAction(BaseAction):
    NAME = "JavaCopyDependencies"
    DESCRIPTION = "Copying dependencies"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, artifacts_dir, dependencies_dir, os_utils):
        self.artifacts_dir = artifacts_dir
        self.dependencies_dir = dependencies_dir
        self.os_utils = os_utils

    def execute(self):
        self._copy_dependencies()

    def _copy_dependencies(self):
        try:
            if not self.os_utils.exists(self.dependencies_dir):
                self.os_utils.makedirs(self.dependencies_dir)
            lib_folder = os.path.join(self.artifacts_dir, "lib")
            self.os_utils.copytree(lib_folder, self.dependencies_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))
