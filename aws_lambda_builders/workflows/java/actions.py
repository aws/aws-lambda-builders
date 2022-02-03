"""
Common Actions for the Java Workflows
"""

import os
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose


class JavaCopyDependenciesAction(BaseAction):
    """
    Class for copying Java dependencies from artifact folder to dependencies folder
    """

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
        """
        copy the entire lib directory from artifact folder to dependencies folder
        """
        try:
            dependencies_lib_dir = os.path.join(self.dependencies_dir, "lib")
            if not self.os_utils.exists(dependencies_lib_dir):
                self.os_utils.makedirs(dependencies_lib_dir)
            lib_folder = os.path.join(self.artifacts_dir, "lib")
            self.os_utils.copytree(lib_folder, dependencies_lib_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))


class JavaMoveDependenciesAction(BaseAction):
    """
    Class for Moving Java dependencies from artifact folder to dependencies folder
    """

    NAME = "JavaMoveDependencies"
    DESCRIPTION = "Move dependencies"
    PURPOSE = Purpose.MOVE_DEPENDENCIES

    def __init__(self, artifacts_dir, dependencies_dir, os_utils):
        self.artifacts_dir = artifacts_dir
        self.dependencies_dir = dependencies_dir
        self.os_utils = os_utils

    def execute(self):
        self._move_dependencies()

    def _move_dependencies(self):
        """
        Move the entire lib directory from artifact folder to dependencies folder
        """
        try:
            dependencies_lib_dir = os.path.join(self.dependencies_dir, "lib")
            lib_folder = os.path.join(self.artifacts_dir, "lib")
            self.os_utils.move(lib_folder, dependencies_lib_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))
