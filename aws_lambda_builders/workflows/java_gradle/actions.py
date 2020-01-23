"""
Actions for the Java Gradle Workflow
"""

import os
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from .gradle import GradleExecutionError


class JavaGradleBuildAction(BaseAction):
    NAME = "GradleBuild"
    DESCRIPTION = "Building the project using Gradle"
    PURPOSE = Purpose.COMPILE_SOURCE

    INIT_SCRIPT = "lambda-build-init.gradle"
    SCRATCH_DIR_PROPERTY = "software.amazon.aws.lambdabuilders.scratch-dir"
    GRADLE_CACHE_DIR_NAME = "gradle-cache"

    def __init__(self, source_dir, build_file, subprocess_gradle, scratch_dir, os_utils):
        self.source_dir = source_dir
        self.build_file = build_file
        self.scratch_dir = scratch_dir
        self.subprocess_gradle = subprocess_gradle
        self.os_utils = os_utils
        self.cache_dir = os.path.join(self.scratch_dir, self.GRADLE_CACHE_DIR_NAME)

    def execute(self):
        init_script_file = self._copy_init_script()
        self._build_project(init_script_file)

    @property
    def gradle_cache_dir(self):
        return self.cache_dir

    def _copy_init_script(self):
        try:
            src = os.path.join(os.path.dirname(__file__), "resources", self.INIT_SCRIPT)
            dst = os.path.join(self.scratch_dir, self.INIT_SCRIPT)
            return self.os_utils.copy(src, dst)
        except Exception as ex:
            raise ActionFailedError(str(ex))

    def _build_project(self, init_script_file):
        try:
            if not self.os_utils.exists(self.scratch_dir):
                self.os_utils.makedirs(self.scratch_dir)
            self.subprocess_gradle.build(
                self.source_dir,
                self.build_file,
                self.gradle_cache_dir,
                init_script_file,
                {self.SCRATCH_DIR_PROPERTY: os.path.abspath(self.scratch_dir)},
            )
        except GradleExecutionError as ex:
            raise ActionFailedError(str(ex))


class JavaGradleCopyArtifactsAction(BaseAction):
    NAME = "CopyArtifacts"
    DESCRIPTION = "Copying the built artifacts"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, artifacts_dir, build_dir, os_utils):
        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.build_dir = build_dir
        self.os_utils = os_utils

    def execute(self):
        self._copy_artifacts()

    def _copy_artifacts(self):
        lambda_build_output = os.path.join(self.build_dir, "build", "distributions", "lambda-build")
        try:
            if not self.os_utils.exists(self.artifacts_dir):
                self.os_utils.makedirs(self.artifacts_dir)
            self.os_utils.copytree(lambda_build_output, self.artifacts_dir)
        except Exception as ex:
            raise ActionFailedError(str(ex))
