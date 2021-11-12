"""
Action to resolve Python dependencies using PIP
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from aws_lambda_builders.architecture import X86_64
from aws_lambda_builders.workflows.python_pip.utils import OSUtils
from .exceptions import MissingPipError
from .packager import PythonPipDependencyBuilder, PackagerError, DependencyBuilder, SubprocessPip, PipRunner


class PythonPipBuildAction(BaseAction):

    NAME = "ResolveDependencies"
    DESCRIPTION = "Installing dependencies from PIP"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES
    LANGUAGE = "python"

    def __init__(
        self, artifacts_dir, scratch_dir, manifest_path, runtime, dependencies_dir, binaries, architecture=X86_64
    ):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.runtime = runtime
        self.dependencies_dir = dependencies_dir
        self.binaries = binaries
        self.architecture = architecture

    def execute(self):
        os_utils = OSUtils()
        python_path = self.binaries[self.LANGUAGE].binary_path
        try:
            pip = SubprocessPip(osutils=os_utils, python_exe=python_path)
        except MissingPipError as ex:
            raise ActionFailedError(str(ex))
        pip_runner = PipRunner(python_exe=python_path, pip=pip)
        dependency_builder = DependencyBuilder(
            osutils=os_utils, pip_runner=pip_runner, runtime=self.runtime, architecture=self.architecture
        )

        package_builder = PythonPipDependencyBuilder(
            osutils=os_utils, runtime=self.runtime, dependency_builder=dependency_builder
        )
        try:
            target_artifact_dir = self.artifacts_dir
            # if dependencies folder is provided, download the dependencies into dependencies folder
            if self.dependencies_dir:
                target_artifact_dir = self.dependencies_dir

            package_builder.build_dependencies(
                artifacts_dir_path=target_artifact_dir,
                scratch_dir_path=self.scratch_dir,
                requirements_path=self.manifest_path,
            )
        except PackagerError as ex:
            raise ActionFailedError(str(ex))
