"""
Rust Cargo Workflow
"""
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from .actions import RustBuildAction, RustCopyAndRenameAction


class RustCargoWorkflow(BaseWorkflow):

    NAME = "RustCargoBuilder"

    CAPABILITY = Capability(language="rust", dependency_manager="cargo", application_framework=None)

    SUPPORTED_MANIFESTS = ["Cargo.toml"]

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, mode=None, **kwargs):
        super(RustCargoWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        # we utilize the handler identifier to
        # select the binary to build
        options = kwargs.get("options") or {}
        handler = options.get("artifact_executable_name", None)
        flags = options.get("cargo_lambda_flags", None)
        self.actions = [
            RustBuildAction(source_dir, self.binaries, mode, self.architecture, handler, flags),
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
