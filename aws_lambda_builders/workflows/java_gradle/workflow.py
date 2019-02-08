"""
Java Gradle Workflow
"""
import hashlib
import os
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from .actions import JavaGradleBuildAction, JavaGradleCopyArtifactsAction
from .gradle import SubprocessGradle
from .gradle_resolver import GradleResolver
from .utils import OSUtils
from .gradle_validator import GradleBinaryValidator


class JavaGradleWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build Java projects using Gradle.
    """
    NAME = "JavaGradleWorkflow"

    CAPABILITY = Capability(language="java",
                            dependency_manager="gradle",
                            application_framework=None)

    INIT_FILE = "lambda-build-init.gradle"

    def __init__(self,
                 source_dir,
                 artifacts_dir,
                 scratch_dir,
                 manifest_path,
                 **kwargs):
        super(JavaGradleWorkflow, self).__init__(source_dir,
                                                 artifacts_dir,
                                                 scratch_dir,
                                                 manifest_path,
                                                 **kwargs)

        self.os_utils = OSUtils()
        self.build_dir = None
        subprocess_gradle = SubprocessGradle(self.binaries['gradle'], self.os_utils)

        self.actions = [
            JavaGradleBuildAction(source_dir,
                                  subprocess_gradle,
                                  scratch_dir,
                                  self.os_utils),
            JavaGradleCopyArtifactsAction(source_dir,
                                          artifacts_dir,
                                          self.build_output_dir,
                                          self.os_utils)
        ]

    def get_resolvers(self):
        return [GradleResolver(self.source_dir, self.os_utils)]

    def get_validators(self):
        return [GradleBinaryValidator(self.os_utils)]

    @property
    def build_output_dir(self):
        if self.build_dir is None:
            self.build_dir = os.path.join(self.scratch_dir, self._compute_scratch_subdir())
        return self.build_dir

    def _compute_scratch_subdir(self):
        sha1 = hashlib.sha1()
        sha1.update(os.path.abspath(self.source_dir).encode('utf8'))
        return sha1.hexdigest()
