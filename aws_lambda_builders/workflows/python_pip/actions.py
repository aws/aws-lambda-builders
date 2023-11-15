"""
Action to resolve Python dependencies using PIP
"""

import logging
from typing import Optional, Tuple

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.architecture import X86_64
from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.exceptions import MisMatchRuntimeError, RuntimeValidatorError
from aws_lambda_builders.workflows.python_pip.exceptions import MissingPipError
from aws_lambda_builders.workflows.python_pip.packager import (
    DependencyBuilder,
    PackagerError,
    PipRunner,
    PythonPipDependencyBuilder,
    SubprocessPip,
)
from aws_lambda_builders.workflows.python_pip.utils import OSUtils

LOG = logging.getLogger(__name__)


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

        self._os_utils = OSUtils()

    def execute(self) -> None:
        """
        Executes the build action for Python `pip` workflows.
        """
        pip, python_with_pip = self._find_runtime_with_pip()
        pip_runner = PipRunner(python_exe=python_with_pip, pip=pip)

        dependency_builder = DependencyBuilder(
            osutils=self._os_utils, pip_runner=pip_runner, runtime=self.runtime, architecture=self.architecture
        )

        package_builder = PythonPipDependencyBuilder(
            osutils=self._os_utils, runtime=self.runtime, dependency_builder=dependency_builder
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

    def _find_runtime_with_pip(self) -> Tuple[SubprocessPip, str]:
        """
        Finds a Python runtime that also contains `pip`.

        Returns
        -------
        Tuple[SubprocessPip, str]
            Returns a tuple of the SubprocessPip object created from
            a valid Python runtime and the runtime path itself

        Raises
        ------
        ActionFailedError
            Raised if the method is not able to find a valid runtime
            that has the correct Python and pip installed
        """
        binary_object: Optional[BinaryPath] = self.binaries.get(self.LANGUAGE)

        if not binary_object:
            raise ActionFailedError("Failed to fetch Python binaries from the PATH.")

        for python_path in binary_object.resolver.exec_paths:
            try:
                valid_python_path = binary_object.validator.validate(python_path)

                if valid_python_path:
                    pip = SubprocessPip(osutils=self._os_utils, python_exe=valid_python_path)

                    return (pip, valid_python_path)
            except (MisMatchRuntimeError, RuntimeValidatorError):
                # runtime and mismatch exceptions should have been caught
                # during the init phase

                # we can ignore these and let the action fail at the end
                LOG.debug(f"Python runtime path '{python_path}' does not match the workflow")
            except MissingPipError:
                LOG.debug(f"Python runtime path '{python_path}' does not contain pip")

        raise ActionFailedError("Failed to find a Python runtime containing pip on the PATH.")
