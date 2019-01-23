"""
Java Gradle Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability
from .actions import JavaGradleBuildAction
from .gradle import SubprocessGradle
from .utils import OSUtils
import os


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
        gradle_exec = self._determine_gradle_exec()
        subprocess_gradle = SubprocessGradle(gradle_exec, self.os_utils)
        artifact_mapping = self._resolve_artifact_mapping()

        self.actions = [
            JavaGradleBuildAction(source_dir,
                                  artifacts_dir,
                                  artifact_mapping,
                                  subprocess_gradle,
                                  scratch_dir,
                                  self.os_utils)
        ]

    def _determine_gradle_exec(self):
        """
        Determine the correct Gradle executable to use. The project's included gradlew script takes precedence.

        :return: The Gradle executable to use for the build.
        """
        gradlew_name = 'gradlew.bat' if self.os_utils.is_windows() else 'gradlew'
        gradlew = os.path.join(self.source_dir, gradlew_name)
        if os.path.exists(gradlew):
            return gradlew
        else:
            # assume Gradle is available on the PATH
            return 'gradle'

    def _resolve_artifact_mapping(self):
        """
        Creates the map from the source of a single Lambda function (under source_dir), to the sub-directory under
        artifacts_dir where the function's artifact is to be placed.

        :return: The artifact mapping.
        """
        if self.options is None or self.options['artifact_mapping'] is None:
            return {'.': '.'}
        return self.options['artifact_mapping']
