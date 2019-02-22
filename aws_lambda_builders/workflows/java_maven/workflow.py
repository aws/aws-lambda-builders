"""
Java Maven Workflow
"""
import os

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.workflows.java_gradle.utils import OSUtils
from aws_lambda_builders.actions import CopySourceAction
from .actions import JavaMavenBuildAction, JavaMavenCopyDependencyAction, JavaMavenCopyArtifactsAction
from .maven import SubprocessMaven
from .maven_resolver import MavenResolver
from .maven_validator import MavenValidator


class JavaMavenWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build Java projects using Maven.
    """
    NAME = "JavaMavenWorkflow"

    CAPABILITY = Capability(language="java",
                            dependency_manager="maven",
                            application_framework=None)

    EXCLUDED_FILES = (".aws-sam")

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 **kwargs):
        super(JavaMavenWorkflow, self).__init__(source_dir,
                                                artifacts_dir,
                                                scratch_dir,
                                                manifest_path,
                                                **kwargs)

        self.os_utils = OSUtils()

        # TODO: Fix root_dir and module_name for multimodule project
        root_dir = None
        # module_name = os.path.basename(os.path.dirname(source_dir))
        module_name = None

        subprocess_maven = SubprocessMaven(maven_binary=self.binaries['mvn'], os_utils=self.os_utils)

        self.actions = [
            CopySourceAction(source_dir, scratch_dir, excludes=self.EXCLUDED_FILES),
            JavaMavenBuildAction(scratch_dir,
                                 subprocess_maven,
                                 module_name,
                                 root_dir),
            JavaMavenCopyDependencyAction(scratch_dir,
                                          subprocess_maven,
                                          module_name,
                                          root_dir),
            JavaMavenCopyArtifactsAction(scratch_dir,
                                         artifacts_dir,
                                         self.os_utils)
        ]

    def get_resolvers(self):
        return [MavenResolver(executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [MavenValidator(self.os_utils)]
