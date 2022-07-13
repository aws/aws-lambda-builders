"""
Rust Cargo build actions
"""

import logging
import os
import subprocess
import shutil

from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.architecture import X86_64, ARM64

LOG = logging.getLogger(__name__)


class RustBuilderError(Exception):
    MESSAGE = "Builder Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class OSUtils(object):
    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        return subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)

    def copyfile(self, source, destination):
        shutil.copyfile(source, destination)

    def makedirs(self, path):
        if not os.path.exists(path):
            os.makedirs(path)


class RustBuildAction(BaseAction):
    NAME = "CargoLambdaBuild"
    DESCRIPTION = "Building the project using Cargo Lambda"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, binaries, mode, architecture=X86_64, handler=None, flags=None, osutils=OSUtils()):
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
            Handler name in `package.bin_name` or `bin_name` format

        :type flags: list, optional
        :param flags:
            Extra list of flags to pass to `cargo lambda build`

        :type osutils: object, optional
        :param osutils:
            Optional, External IO utils
        """
        self._source_dir = source_dir
        self._mode = mode
        self._binaries = binaries
        self._handler = handler
        self._flags = flags
        self._architecture = architecture
        self._osutils = osutils

    def build_command(self):
        cmd = [self._binaries["cargo"].binary_path, "lambda", "build"]
        if self._mode == BuildMode.RELEASE:
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
            command = self.build_command()
            LOG.debug("Executing cargo-lambda: %s", " ".join(command))
            if LOG.isEnabledFor(logging.DEBUG):
                os.environ["RUST_LOG"] = "debug"

            p = self._osutils.popen(
                command,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                cwd=self._source_dir,
            )
            out, err = p.communicate()
            if p.returncode != 0:
                raise RustBuilderError(message=err.decode("utf8").strip())
            return out.decode("utf8").strip()
        except Exception as ex:
            raise ActionFailedError(str(ex))


class RustCopyAndRenameAction(BaseAction):
    NAME = "RustCopyAndRename"
    DESCRIPTION = "Copy Rust executable, renaming if needed"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, artifacts_dir, handler=None, osutils=OSUtils()):
        """
        Copy and rename Rust executable

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type artifacts_dir: str
        :param binaries:
            Path to a folder containing the deployable artifacts

        :type handler: str, optional
        :param handler:
            Handler name in `package.bin_name` or `bin_name` format

        :type osutils: object
        :param osutils:
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

        LOG.debug("unexpected list of binary directories: [%s]" ", ".join(output))
        raise RustBuilderError(
            message="unable to find function binary, use the option `artifact_executable_name` to specify the binary's name"
        )

    def execute(self):
        self._osutils.makedirs(self._artifacts_dir)
        binary_path = self.binary_path()
        destination_path = os.path.join(self._artifacts_dir, "bootstrap")
        LOG.debug("copying function binary from %s to %s", binary_path, destination_path)
        self._osutils.copyfile(binary_path, destination_path)
