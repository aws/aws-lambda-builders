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

    def build_command(self):
        cmd = [self._binaries["cargo"].binary_path, "lambda", "build"]
        if self._mode != BuildMode.DEBUG:
            cmd.append("--release")
        if self._architecture == ARM64:
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

    def __init__(self, source_dir, artifacts_dir, handler=None, osutils=OSUtils()):
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

        osutils : aws_lambda_builders.workflows.rust_cargo.utils.OSUtils, optional
            Optional, External IO utils
        """
        self._source_dir = source_dir
        self._handler = handler
        self._artifacts_dir = artifacts_dir
        self._osutils = osutils

    def base_path(self):
        return os.path.join(self._source_dir, "target", "lambda")

    def binary_path(self):
        base = self.base_path()
        if self._handler:
            binary_path = os.path.join(base, self._handler, "bootstrap")
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
