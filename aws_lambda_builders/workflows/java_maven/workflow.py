"""
Java Maven Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.actions import CopySourceAction
from .actions import JavaMavenBuildAction, JavaMavenCopyDependencyAction, JavaMavenCopyArtifactsAction
from .maven import SubprocessMaven
from .maven_resolver import MavenResolver
from .maven_validator import MavenValidator
from .utils import OSUtils


class JavaMavenWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build Java projects using Maven.
    """

    NAME = "JavaMavenWorkflow"

    CAPABILITY = Capability(language="java", dependency_manager="maven", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, **kwargs):
        super(JavaMavenWorkflow, self).__init__(source_dir, artifacts_dir, scratch_dir, manifest_path, **kwargs)

        self.os_utils = OSUtils()
        # Assuming root_dir is the same as source_dir for now
        root_dir = source_dir
        subprocess_maven = SubprocessMaven(maven_binary=self.binaries["mvn"], os_utils=self.os_utils)

        self.actions = [
            CopySourceAction(root_dir, scratch_dir, excludes=self.EXCLUDED_FILES),
            JavaMavenBuildAction(scratch_dir, subprocess_maven),
            JavaMavenCopyDependencyAction(scratch_dir, subprocess_maven),
            JavaMavenCopyArtifactsAction(scratch_dir, artifacts_dir, self.os_utils),
        ]

    def get_resolvers(self):
        return [MavenResolver(executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [MavenValidator(self.runtime, self.os_utils)]
