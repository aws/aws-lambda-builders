"""
Rust Cargo build actions
"""

import os
import subprocess
import shutil
import json

from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose

DEFAULT_CARGO_TARGET = "x86_64-unknown-linux-gnu"


class BuilderError(Exception):
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


class BuildAction(BaseAction):
    NAME = "CargoBuild"
    DESCRIPTION = "Building the project using Cargo Lambda"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, handler, binaries, mode, target=DEFAULT_CARGO_TARGET, osutils=OSUtils()):
        """
        Build the a rust executable

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type handler: str
        :param handler:
            Handler name in `bin_name` format

        :type binaries: dict
        :param binaries:
            Resolved path dependencies

        :type mode: str
        :param mode:
            Mode the build should produce

        :type target: str
        :param target:
            Target architecture to build the binary

        :type osutils: object
        :param osutils:
            Optional, External IO utils
        """
        self.source_dir = source_dir
        self.handler = handler
        self.mode = mode
        self.binaries = binaries
        self.target = target
        self.osutils = osutils

    def build_command(self):
        cmd = [self.binaries["cargo"].binary_path, "lambda", "build", "--bin", self.handler, "--target", self.target]
        if self.mode == BuildMode.RELEASE:
            cmd.append("--release")
        return cmd

    def execute(self):
        try:
            p = self.osutils.popen(
                self.build_command(),
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                cwd=self.source_dir,
            )
            out, err = p.communicate()
            if p.returncode != 0:
                raise BuilderError(message=err.decode("utf8").strip())
            return out.decode("utf8").strip()
        except Exception as ex:
            raise ActionFailedError(str(ex))


class CopyAndRenameAction(BaseAction):
    NAME = "CopyAndRename"
    DESCRIPTION = "Copy executable renaming if needed"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, handler, artifacts_dir, platform, mode, osutils=OSUtils()):
        """
        Copy and rename rust executable

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type handler: str
        :param handler:
            Handler name in `package.bin_name` or `bin_name` format

        :type artifacts_dir: str
        :param binaries:
            Path to a folder containing the deployable artifacts

        :type platform: string
        :param platform:
            Platform builder is being run on

        :type mode: str
        :param mode:
            Mode the build should produce

        :type osutils: object
        :param osutils:
            Optional, External IO utils
        """
        self.source_dir = source_dir
        self.handler = handler
        self.artifacts_dir = artifacts_dir
        self.platform = platform
        self.mode = mode
        self.osutils = osutils

    def binary_path(self):
        target = os.path.join(self.source_dir, "target", "lambda", self.handler)
        return os.path.join(target, "bootstrap")

    def execute(self):
        self.osutils.makedirs(self.artifacts_dir)
        self.osutils.copyfile(self.binary_path(), os.path.join(self.artifacts_dir, "bootstrap"))
