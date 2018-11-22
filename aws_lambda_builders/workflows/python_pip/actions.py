"""
Action to resolve Python dependencies using PIP
"""

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from aws_lambda_builders.workflows.python_pip.utils import OSUtils
from .packager import PythonPipDependencyBuilder, PackagerError, DependencyBuilder, SubprocessPip, PipRunner


class PythonPipBuildAction(BaseAction):

    NAME = 'ResolveDependencies'
    DESCRIPTION = "Installing dependencies from PIP"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, manifest_path, scratch_dir, runtime, runtime_path):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.runtime = runtime
        self.language_exec_path = runtime_path
        self.pip = SubprocessPip(osutils=OSUtils(), python_exe=runtime_path)
        self.pip_runner = PipRunner(python_exe=runtime_path, pip=self.pip)
        self.package_builder = PythonPipDependencyBuilder(
            dependency_builder=DependencyBuilder(osutils=OSUtils(),
                pip_runner=self.pip_runner))

    def execute(self):
        try:
            # import ipdb
            # ipdb.set_trace()
            self.package_builder.build_dependencies(
                self.artifacts_dir,
                self.manifest_path,
                self.scratch_dir,
                self.runtime,
            )
        except PackagerError as ex:
            raise ActionFailedError(str(ex))
