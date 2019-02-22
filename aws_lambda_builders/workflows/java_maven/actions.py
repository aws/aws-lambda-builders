"""
Actions for the Java Gradle Workflow
"""

import os

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from .maven import MavenExecutionError


class JavaMavenBuildAction(BaseAction):
    NAME = "MavenBuild"
    DESCRIPTION = "Building the project using Maven"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self,
                 source_dir,
                 subprocess_maven,
                 module_name=None,
                 root_dir=None):
        self.source_dir = source_dir
        self.subprocess_maven = subprocess_maven
        self.module_name = module_name
        self.root_dir = root_dir

    def execute(self):
        try:
            self.subprocess_maven.build(self.source_dir,
                                        self.module_name,
                                        self.root_dir)
        except MavenExecutionError as ex:
            raise ActionFailedError(str(ex))

class JavaMavenCopyDependencyAction(BaseAction):
    NAME = "MavenCopyDependency"
    DESCRIPTION = "Copy dependency jars to target directory"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self,
                 source_dir,
                 subprocess_maven,
                 module_name=None,
                 root_dir=None):
        self.source_dir = source_dir
        self.subprocess_maven = subprocess_maven
        self.module_name = module_name
        self.root_dir = root_dir

    def execute(self):
        try:
            self.subprocess_maven.copy_dependency(self.source_dir,
                                                  self.module_name,
                                                  self.root_dir)
        except MavenExecutionError as ex:
            raise ActionFailedError(str(ex))

class JavaMavenCopyArtifactsAction(BaseAction):
    NAME = "MavenCopyArtifacts"
    DESCRIPTION = "Copying the built artifacts"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 os_utils):
        self.artifacts_dir = artifacts_dir
        self.source_dir = source_dir
        self.os_utils = os_utils

    def execute(self):
        self._copy_artifacts()

    def _copy_artifacts(self):
        lambda_build_output = os.path.join(self.source_dir, 'target', 'classes')
        dependency_output = os.path.join(self.source_dir, 'target', 'dependency')

        try:
            self.os_utils.copytree(lambda_build_output, self.artifacts_dir)
            if self.os_utils.exists(dependency_output):
                self.os_utils.copytree(dependency_output, os.path.join(self.artifacts_dir, 'lib'))
        except Exception as ex:
            raise ActionFailedError(str(ex))
