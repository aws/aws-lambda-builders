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
            dependencies_lib_dir = os.path.join(self.dependencies_dir, "lib")
            if not self.os_utils.exists(dependencies_lib_dir):
                self.os_utils.makedirs(dependencies_lib_dir)
            lib_folder = os.path.join(self.artifacts_dir, "lib")
            self.os_utils.copytree(lib_folder, dependencies_lib_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))


class JavaRemoveDependenciesAction(BaseAction):
    NAME = "JavaRemoveDependencies"
    DESCRIPTION = "Remove dependencies"
    PURPOSE = Purpose.REMOVE_DEPENDENCIES

    def __init__(self, artifacts_dir, os_utils):
        self.artifacts_dir = artifacts_dir
        self.os_utils = os_utils

    def execute(self):
        self._remove_dependencies()

    def _remove_dependencies(self):
        try:
            artifacts_lib_dir = os.path.join(self.artifacts_dir, "lib")
            if self.os_utils.exists(artifacts_lib_dir):
                self.os_utils.rmtree(artifacts_lib_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))
