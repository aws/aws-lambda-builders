"""
Java Maven Workflow
"""
import os

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from aws_lambda_builders.workflows.java_gradle.utils import OSUtils
from .actions import JavaMavenBuildAction, JavaMavenCopyDependencyAction, JavaMavenCopyArtifactsAction, \
    JavaMavenCleanupAction
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

        # TODO: Fix this
        root_dir = None

        subprocess_maven = SubprocessMaven(maven_binary=self.binaries['maven'], os_utils=self.os_utils)
        module_name = os.path.basename(os.path.dirname(source_dir))

        self.actions = [
            JavaMavenBuildAction(source_dir,
                                 subprocess_maven,
                                 module_name,
                                 root_dir),
            JavaMavenCopyDependencyAction(source_dir,
                                          subprocess_maven,
                                          module_name,
                                          root_dir),
            JavaMavenCopyArtifactsAction(artifacts_dir,
                                         source_dir,
                                         self.os_utils),
            JavaMavenCleanupAction(source_dir,
                                   subprocess_maven,
                                   module_name,
                                   root_dir)
        ]

    def get_resolvers(self):
        return [MavenResolver(executable_search_paths=self.executable_search_paths)]

    def get_validators(self):
        return [MavenValidator(self.os_utils)]
