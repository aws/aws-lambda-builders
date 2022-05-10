"""
Java Gradle Workflow
"""
import hashlib
import os
from aws_lambda_builders.actions import CleanUpAction
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.workflows.java.actions import JavaCopyDependenciesAction, JavaMoveDependenciesAction
from aws_lambda_builders.workflows.java.utils import OSUtils

from .actions import JavaGradleBuildAction, JavaGradleCopyArtifactsAction, JavaGradleCopyLayerArtifactsAction
from .gradle import SubprocessGradle
from .gradle_resolver import GradleResolver
from .gradle_validator import GradleValidator


class JavaGradleWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build Java projects using Gradle.
    """

    NAME = "JavaGradleWorkflow"

    CAPABILITY = Capability(language="java", dependency_manager="gradle", application_framework=None)

    INIT_FILE = "lambda-build-init.gradle"

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, **kwargs):
        super(JavaGradleWorkflow, self).__init__(source_dir, artifacts_dir, scratch_dir, manifest_path, **kwargs)

        self.os_utils = OSUtils()
        self.build_dir = None

        subprocess_gradle = SubprocessGradle(gradle_binary=self.binaries["gradle"], os_utils=self.os_utils)

        copy_artifacts_action = JavaGradleCopyArtifactsAction(
            source_dir, artifacts_dir, self.build_output_dir, self.os_utils
        )
        if self.is_building_layer:
            copy_artifacts_action = JavaGradleCopyLayerArtifactsAction(
                source_dir, artifacts_dir, self.build_output_dir, self.os_utils
            )
        self.actions = [
            JavaGradleBuildAction(source_dir, manifest_path, subprocess_gradle, scratch_dir, self.os_utils),
            copy_artifacts_action,
        ]

        if self.dependencies_dir:
            # clean up the dependencies first
            self.actions.append(CleanUpAction(self.dependencies_dir))

            if self.combine_dependencies:
                self.actions.append(JavaCopyDependenciesAction(artifacts_dir, self.dependencies_dir, self.os_utils))
            else:
                self.actions.append(JavaMoveDependenciesAction(artifacts_dir, self.dependencies_dir, self.os_utils))

    def get_resolvers(self):
        return [GradleResolver(executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [GradleValidator(self.runtime, self.architecture, self.os_utils)]

    @property
    def build_output_dir(self):
        if self.build_dir is None:
            self.build_dir = os.path.join(self.scratch_dir, self._compute_scratch_subdir())
        return self.build_dir

    def _compute_scratch_subdir(self):
        """
        Compute where the init script will instruct Gradle to place the built artifacts for the lambda within
        `scratch_dir`; i.e. the that it will set for 'project.buildDir`.

        :return: The path of the buildDir used for building the lambda.
        """
        sha1 = hashlib.sha1()
        sha1.update(os.path.abspath(self.source_dir).encode("utf8"))
        return sha1.hexdigest()
