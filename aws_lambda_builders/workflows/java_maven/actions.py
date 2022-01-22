"""
Actions for the Java Maven Workflow
"""

import os
import logging
import shutil

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from .maven import MavenExecutionError
from ..java.utils import jar_file_filter

LOG = logging.getLogger(__name__)


class JavaMavenBaseAction(object):
    """
    Base class for Java Maven actions. Provides property of the module name
    """

    def __init__(self, scratch_dir, subprocess_maven):
        self.scratch_dir = scratch_dir
        self.subprocess_maven = subprocess_maven


class JavaMavenBuildAction(JavaMavenBaseAction, BaseAction):
    NAME = "MavenBuild"
    DESCRIPTION = "Building the project using Maven"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, scratch_dir, subprocess_maven):
        super(JavaMavenBuildAction, self).__init__(scratch_dir, subprocess_maven)
        self.scratch_dir = scratch_dir
        self.subprocess_maven = subprocess_maven

    def execute(self):
        try:
            self.subprocess_maven.build(self.scratch_dir)
        except MavenExecutionError as ex:
            raise ActionFailedError(str(ex))


class JavaMavenCopyDependencyAction(JavaMavenBaseAction, BaseAction):
    NAME = "MavenCopyDependency"
    DESCRIPTION = "Copy dependency jars to target directory"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, scratch_dir, subprocess_maven):
        super(JavaMavenCopyDependencyAction, self).__init__(scratch_dir, subprocess_maven)
        self.scratch_dir = scratch_dir
        self.subprocess_maven = subprocess_maven

    def execute(self):
        try:
            self.subprocess_maven.copy_dependency(self.scratch_dir)
        except MavenExecutionError as ex:
            raise ActionFailedError(str(ex))


class JavaMavenCopyArtifactsAction(BaseAction):
    NAME = "MavenCopyArtifacts"
    DESCRIPTION = "Copying the built artifacts"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, scratch_dir, artifacts_dir, os_utils):
        self.scratch_dir = scratch_dir
        self.artifacts_dir = artifacts_dir
        self.os_utils = os_utils

    def execute(self):
        self._copy_artifacts()

    def _copy_artifacts(self):
        lambda_build_output = os.path.join(self.scratch_dir, "target", "classes")
        dependency_output = os.path.join(self.scratch_dir, "target", "dependency")

        if not self.os_utils.exists(lambda_build_output):
            raise ActionFailedError("Required target/classes directory was not produced from 'mvn package'")

        try:
            self.os_utils.copytree(lambda_build_output, self.artifacts_dir)
            if self.os_utils.exists(dependency_output):
                self.os_utils.copytree(dependency_output, os.path.join(self.artifacts_dir, "lib"))
        except Exception as ex:
            raise ActionFailedError(str(ex))


class JavaMavenCopyLayerArtifactsAction(JavaMavenCopyArtifactsAction):
    """
    Java layers does not support using .class files in it.
    This action (different from the parent one) copies contents of the layer as jar files and place it
    into the artifact folder
    """

    NAME = "MavenCopyLayerArtifacts"
    IGNORED_FOLDERS = ["classes", "dependency", "generated-sources", "maven-archiver", "maven-status"]

    def _copy_artifacts(self):
        lambda_build_output = os.path.join(self.scratch_dir, "target")
        dependency_output = os.path.join(self.scratch_dir, "target", "dependency")

        if not self.os_utils.exists(lambda_build_output):
            raise ActionFailedError("Required target/classes directory was not produced from 'mvn package'")

        try:
            self.os_utils.copytree(
                lambda_build_output,
                os.path.join(self.artifacts_dir, "lib"),
                ignore=shutil.ignore_patterns(*self.IGNORED_FOLDERS),
                include=jar_file_filter,
            )
            if self.os_utils.exists(dependency_output):
                self.os_utils.copytree(dependency_output, os.path.join(self.artifacts_dir, "lib"))
        except Exception as ex:
            raise ActionFailedError(str(ex))
