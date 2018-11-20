"""
Actions for the Rust Cargo workflow
"""
import subprocess
import logging
import sys
import os
import shutil
import platform

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .cargo import CargoParser, CargoFileNotFoundError, CargoParsingError, CargoValidationError, ExecutableNotFound

LOG = logging.getLogger(__name__)
TARGET_PLATFORM = "x86_64-unknown-linux-musl"

class CargoValidator(BaseAction):
    """
    Validates that Cargo.toml is configured correclty to build a Lambda application
    """
    NAME = 'CargoValidator'
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, source_dir, manifest_path, runtime):
        self.source_dir = source_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.cargo_parser = CargoParser(manifest_path)

    def execute(self):
        try:
            self.cargo_parser.validate(print_warnings=True)
        except (CargoFileNotFoundError, CargoParsingError, CargoValidationError) as ex:
            raise ActionFailedError(str(ex))

class RustCargoBuildAction(BaseAction):
    """
    Uses Cargo to build a project
    """
    NAME = 'RustCargoBuildAction'
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, manifest_path, runtime):
        self.source_dir = source_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.cargo_parser = CargoParser(manifest_path)

    def execute(self):
        try:
            LOG.info("Starting cargo release build for %s", self.source_dir)
            cmd = "cargo build --release --target " + TARGET_PLATFORM
            subprocess.run(
                cmd,
                stderr=sys.stderr,
                stdout=sys.stderr,
                shell=True,
                cwd=self.source_dir,
                check=True,
            )
            LOG.info("Built executable: %s", self.cargo_parser.get_executable_name())
            #LOG.info("Done: %s", build_output)
        except subprocess.CalledProcessError as ex:
            LOG.info("Error while executing build: %i\n%s", ex.returncode, ex.output)
            raise ActionFailedError(str(ex))

class CopyAndRenameExecutableAction(BaseAction):
    NAME = 'CopyAndRenameExecutableAction'
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, atrifact_path, manifest_path, runtime):
        self.source_dir = source_dir
        self.manifest_path = manifest_path
        self.artifact_path = atrifact_path
        self.runtime = runtime
        self.cargo_parser = CargoParser(manifest_path)

    def execute(self):
        try:
            bin_path = self.cargo_parser.get_executable_path(TARGET_PLATFORM)
            LOG.info("Copying executable from %s to %s", bin_path, self.artifact_path)
            shutil.copyfile(bin_path, self.artifact_path, follow_symlinks=True)
        except ExecutableNotFound as ex:
            raise ActionFailedError(str(ex))
        except (OSError, shutil.SpecialFileError) as ex:
            raise ActionFailedError(str(ex))
