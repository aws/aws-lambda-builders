"""
Actions for the Java Gradle Workflow
"""

import os
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from .gradle import GradleExecutionError


class JavaGradleBuildAction(BaseAction):
    NAME = "JavaGradle"
    DESCRIPTION = "Building the project using Gradle"
    PURPOSE = Purpose.COMPILE_SOURCE

    INIT_SCRIPT = 'lambda-build-init.gradle'

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 artifact_mapping,
                 subprocess_gradle,
                 scratch_dir,
                 os_utils):
        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.artifact_mapping = artifact_mapping
        self.scratch_dir = scratch_dir
        self.subprocess_gradle = subprocess_gradle
        self.os_utils = os_utils

    def execute(self):
        init_script_file = self._copy_init_script()
        self._build_project(init_script_file)
        self._copy_artifacts()

    def _copy_init_script(self):
        try:
            src = os.path.join(os.path.dirname(__file__), 'resources', self.INIT_SCRIPT)
            dst = os.path.join(self.scratch_dir, self.INIT_SCRIPT)
            return self.os_utils.copy(src, dst)
        except Exception as ex:
            raise ActionFailedError(str(ex))

    def _build_project(self, init_script_file):
        try:
            self.subprocess_gradle.build(self.source_dir, init_script_file)
        except GradleExecutionError as ex:
            raise ActionFailedError(str(ex))

    def _copy_artifacts(self):
        try:
            zip_dir = os.path.join('build', 'distributions', 'lambda-build')
            for src_sub_dir, artifacts_sub_dir in self.artifact_mapping.items():
                src = os.path.join(self.source_dir, src_sub_dir, zip_dir)
                dst = os.path.join(self.artifacts_dir, artifacts_sub_dir)
                for f in self.os_utils.listdir(src):
                    self.os_utils.copy(os.path.join(src, f), os.path.join(dst, f))
        except Exception as ex:
            raise ActionFailedError(str(ex))
