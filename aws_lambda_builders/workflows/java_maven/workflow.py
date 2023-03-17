"""
Java Maven Workflow
"""
from aws_lambda_builders.actions import CleanUpAction, CopySourceAction
from aws_lambda_builders.workflow import BaseWorkflow, BuildDirectory, BuildInSourceSupport, Capability
from aws_lambda_builders.workflows.java.actions import JavaCopyDependenciesAction, JavaMoveDependenciesAction
from aws_lambda_builders.workflows.java.utils import OSUtils

from .actions import (
    JavaMavenBuildAction,
    JavaMavenCopyArtifactsAction,
    JavaMavenCopyDependencyAction,
    JavaMavenCopyLayerArtifactsAction,
)
from .maven import SubprocessMaven
from .maven_resolver import MavenResolver
from .maven_validator import MavenValidator


class JavaMavenWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build Java projects using Maven.
    """

    NAME = "JavaMavenWorkflow"

    CAPABILITY = Capability(language="java", dependency_manager="maven", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    DEFAULT_BUILD_DIR = BuildDirectory.SCRATCH
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.NOT_SUPPORTED

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, **kwargs):
        super(JavaMavenWorkflow, self).__init__(source_dir, artifacts_dir, scratch_dir, manifest_path, **kwargs)

        self.os_utils = OSUtils()
        # Assuming root_dir is the same as source_dir for now
        root_dir = source_dir
        subprocess_maven = SubprocessMaven(
            maven_binary=self.binaries["mvn"],
            os_utils=self.os_utils,
        )

        copy_artifacts_action = JavaMavenCopyArtifactsAction(scratch_dir, artifacts_dir, self.os_utils)
        if self.is_building_layer:
            copy_artifacts_action = JavaMavenCopyLayerArtifactsAction(scratch_dir, artifacts_dir, self.os_utils)

        self.actions = [
            CopySourceAction(root_dir, scratch_dir, excludes=self.EXCLUDED_FILES),
            JavaMavenBuildAction(scratch_dir, subprocess_maven),
            JavaMavenCopyDependencyAction(scratch_dir, subprocess_maven),
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
        return [MavenResolver(executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [MavenValidator(self.runtime, self.architecture, self.os_utils)]
