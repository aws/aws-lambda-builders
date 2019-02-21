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
                 module_name,
                 root_dir):
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
                 module_name,
                 root_dir):
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
    NAME = "CopyArtifacts"
    DESCRIPTION = "Copying the built artifacts"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self,
                 artifacts_dir,
                 source_dir,
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
            if not self.os_utils.exists(self.artifacts_dir):
                self.os_utils.makedirs(self.artifacts_dir)
            self.os_utils.copytree(lambda_build_output, self.artifacts_dir)
            self.os_utils.copytree(dependency_output, self.artifacts_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))

class JavaMavenCleanupAction(BaseAction):
    NAME = "CleanUpArtifacts"
    DESCRIPTION = "Clean up target directory"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self,
                 source_dir,
                 subprocess_maven,
                 module_name,
                 root_dir):
        self.source_dir = source_dir
        self.subprocess_maven = subprocess_maven
        self.module_name = module_name
        self.root_dir = root_dir

    def execute(self):
        try:
            self.subprocess_maven.cleanup(self.source_dir, self.module_name, self.root_dir)
        except MavenExecutionError as ex:
            raise ActionFailedError(str(ex))
