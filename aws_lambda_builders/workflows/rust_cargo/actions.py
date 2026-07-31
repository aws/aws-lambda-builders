"""
Rust Cargo build actions
"""

import logging
import os

from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.workflow import BuildMode

from .exceptions import CargoLambdaExecutionException
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class RustCargoLambdaBuildAction(BaseAction):
    NAME = "CargoLambdaBuild"
    DESCRIPTION = "Building the project using Cargo Lambda"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(
        self,
        source_dir,
        binaries,
        mode,
        subprocess_cargo_lambda,
        runtime=None,
        architecture=X86_64,
        handler=None,
        flags=None,
    ):
        """
        Build the a Rust executable

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type binaries: dict
        :param binaries:
            Resolved path dependencies

        :type mode: str
        :param mode:
            Mode the build should produce

        :type architecture: str, optional
        :param architecture:
            Target architecture to build the binary, either arm64 or x86_64

        :type handler: str, optional
        :param handler:
            Handler name in `bin_name` format

        :type flags: list, optional
        :param flags:
            Extra list of flags to pass to `cargo lambda build`

        :type subprocess_cargo_lambda: aws_lambda_builders.workflows.rust_cargo.cargo_lambda.SubprocessCargoLambda
        :param subprocess_cargo_lambda: An instance of the Cargo Lambda process wrapper
        """

        self._source_dir = source_dir
        self._mode = mode
        self._binaries = binaries
        self._handler = handler
        self._flags = flags
        self._architecture = architecture
        self._subprocess_cargo_lambda = subprocess_cargo_lambda
        self._runtime = runtime

    def build_command(self):
        cmd = [self._binaries["cargo"].binary_path, "lambda", "build"]
        if self._mode != BuildMode.DEBUG:
            cmd.append("--release")
        # Provided.al2 runtime only has GLIB_2.26 and cargo lambda builds with a higher version by default
        if self._runtime == "provided.al2":
            if self._architecture == ARM64:
                # We cant use the --arm shortcut because then the incorrect version of GLIBC is used
                cmd.append("--target")
                cmd.append("aarch64-unknown-linux-gnu.2.26")
            if self._architecture == X86_64:
                cmd.append("--target")
                cmd.append("x86_64-unknown-linux-gnu.2.26")
        elif self._architecture == ARM64:
            cmd.append("--arm64")
        if self._handler:
            cmd.extend(["--bin", self._handler])
        if self._flags:
            cmd.extend(self._flags)
        return cmd

    def execute(self):
        try:
            return self._subprocess_cargo_lambda.run(command=self.build_command(), cwd=self._source_dir)
        except CargoLambdaExecutionException as ex:
            raise ActionFailedError(str(ex))


class RustCopyAndRenameAction(BaseAction):
    NAME = "RustCopyAndRename"
    DESCRIPTION = "Copy Rust executable, renaming if needed"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(
        self, source_dir, artifacts_dir, handler=None, binaries=None, subprocess_cargo_lambda=None, osutils=OSUtils()
    ):
        """
        Copy and rename Rust executable

        Parameters
        ----------
        source_dir : str
            Path to a folder containing the source code

        artifacts_dir : str
            Path to a folder containing the deployable artifacts

        handler : str, optional
            Handler name in `package.bin_name` or `bin_name` format

        binaries : dict, optional
            Resolved path dependencies, used to locate the `cargo` binary when
            resolving the workspace target directory

        subprocess_cargo_lambda : aws_lambda_builders.workflows.rust_cargo.cargo_lambda.SubprocessCargoLambda, optional
            The Cargo Lambda process wrapper, used to resolve the same target
            directory the build action compiled into

        osutils : aws_lambda_builders.workflows.rust_cargo.utils.OSUtils, optional
            Optional, External IO utils
        """
        self._source_dir = source_dir
        self._handler = handler
        self._artifacts_dir = artifacts_dir
        self._binaries = binaries
        self._subprocess_cargo_lambda = subprocess_cargo_lambda
        self._osutils = osutils

    def _workspace_layout(self):
        # Resolve the same shared target directory and binary name the build action
        # used, from a single cached cargo metadata call. Returns None when the
        # cargo wrapper is unavailable (e.g. in unit tests exercising the legacy path).
        if self._subprocess_cargo_lambda and self._binaries and self._binaries.get("cargo"):
            return self._subprocess_cargo_lambda.resolve_workspace_layout(
                self._binaries["cargo"].binary_path, self._source_dir
            )
        return None

    def base_path(self):
        # For a workspace member this is the workspace root's shared target/lambda; for
        # a standalone project it is source_dir/target/lambda, matching the legacy path.
        layout = self._workspace_layout()
        if layout and layout.get("target_directory"):
            return os.path.join(layout["target_directory"], "lambda")
        return os.path.join(self._source_dir, "target", "lambda")

    def binary_path(self):
        base = self.base_path()

        # An explicit handler (artifact_executable_name) always wins.
        binary_name = self._handler
        # Otherwise use the bin name cargo reported for this member. This is what lets
        # the copy step pick the right binary now that every member shares one
        # target/lambda directory holding all of the workspace's binaries.
        if not binary_name:
            layout = self._workspace_layout()
            if layout:
                binary_name = layout.get("binary_name")

        if binary_name:
            binary_path = os.path.join(base, binary_name, "bootstrap")
            LOG.debug("copying function binary from %s", binary_path)
            return binary_path

        output = os.listdir(base)
        if len(output) == 1:
            binary_path = os.path.join(base, output[0], "bootstrap")
            LOG.debug("copying function binary from %s", binary_path)
            return binary_path

        LOG.warning("unexpected list of binary directories: [%s]", ", ".join(output))
        raise CargoLambdaExecutionException(
            message="unable to find function binary, use the option `artifact_executable_name` to specify the name"
        )

    def execute(self):
        self._osutils.makedirs(self._artifacts_dir)
        binary_path = self.binary_path()
        destination_path = os.path.join(self._artifacts_dir, "bootstrap")
        LOG.debug("copying function binary from %s to %s", binary_path, destination_path)
        self._osutils.copyfile(binary_path, destination_path)
