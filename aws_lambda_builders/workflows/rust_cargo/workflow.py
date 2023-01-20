"""
Rust Cargo Workflow
"""

from aws_lambda_builders.utils import which
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, Capability, BuildInSourceSupport
from .actions import RustCargoLambdaBuildAction, RustCopyAndRenameAction
from .cargo_lambda import SubprocessCargoLambda
from .exceptions import CargoLambdaExecutionException
from .feature_flag import is_experimental_cargo_lambda_scope


class RustCargoLambdaWorkflow(BaseWorkflow):
    NAME = "RustCargoLambdaBuilder"

    CAPABILITY = Capability(language="rust", dependency_manager="cargo", application_framework=None)

    BUILD_IN_SOURCE_BY_DEFAULT = True
    BUILD_IN_SOURCE_SUPPORT = BuildInSourceSupport.EXCLUSIVELY_SUPPORTED

    SUPPORTED_MANIFESTS = ["Cargo.toml"]

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, mode=None, **kwargs):
        super(RustCargoLambdaWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )
        if not is_experimental_cargo_lambda_scope(self.experimental_flags):
            raise CargoLambdaExecutionException(
                message="Feature flag `experimentalCargoLambda` must be enabled to use this workflow"
            )

        # we utilize the handler identifier to
        # select the binary to build
        options = kwargs.get("options") or {}
        handler = options.get("artifact_executable_name", None)
        flags = options.get("cargo_lambda_flags", None)
        subprocess_cargo_lambda = SubprocessCargoLambda(which=which)
        self.actions = [
            RustCargoLambdaBuildAction(
                source_dir,
                self.binaries,
                mode,
                self.architecture,
                handler,
                flags,
                subprocess_cargo_lambda=subprocess_cargo_lambda,
            ),
            RustCopyAndRenameAction(source_dir, artifacts_dir, handler),
        ]

    def get_resolvers(self):
        """
        specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [
            PathResolver(runtime=self.runtime, binary="cargo"),
            PathResolver(runtime=self.runtime, binary="cargo-lambda"),
        ]
