"""
Rust Cargo build actions
"""

import os
import subprocess
import shutil
import json

from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose

CARGO_TARGET = "x86_64-unknown-linux-musl"


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


def parse_handler(handler):
    """
    Parse package and binary from handler name

    If the handler contains a period, assume `package.bin_name`
    otherwise assume common case where bin_name is the same as the package
    """
    spec = handler.split(".", 1)
    if len(spec) == 1:
        return (spec[0], spec[0])
    else:
        return (spec[0], spec[1])


class BuildAction(BaseAction):
    NAME = "CargoBuild"
    DESCRIPTION = "Building the project using Cargo"
    PURPOSE = Purpose.COMPILE_SOURCE

    def __init__(self, source_dir, handler, binaries, platform, mode, osutils=OSUtils()):
        """
        Build the a rust executable

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type handler: str
        :param handler:
            Handler name in `package.bin_name` or `bin_name` format

        :type binaries: dict
        :param binaries:
            Resolved path dependencies

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
        self.mode = mode
        self.binaries = binaries
        self.platform = platform
        self.osutils = osutils

    def cargo_metadata(self):
        p = self.osutils.popen(
            ["cargo", "metadata", "--no-deps", "--format-version=1"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=os.environ.copy(),
            cwd=self.source_dir,
        )
        out, err = p.communicate()
        if p.returncode != 0:
            raise BuilderError(message=err.decode("utf8").strip())
        return json.loads(out)

    def build_command(self, package):
        cmd = [self.binaries["cargo"].binary_path, "build", "-p", package, "--target", CARGO_TARGET]
        if self.mode != BuildMode.DEBUG:
            cmd.append("--release")
        return cmd

    def resolve_binary(self, cargo_meta):
        """
        Interrogate cargo metadata to resolve a handler function

        :type cargo_meta: dict
        :param cargo_meta:
            Build metadata emitted by cargo
        """
        (package, binary) = parse_handler(self.handler)
        exists = any(
            [
                kind == "bin"
                for pkg in cargo_meta["packages"]
                if pkg["name"] == package
                for target in pkg["targets"]
                if target["name"] == binary
                for kind in target["kind"]
            ]
        )
        if not exists:
            raise BuilderError(message="Cargo project does not contain a {handler} binary".format(handler=self.handler))

        return (package, binary)

    def build_env(self):
        env = os.environ.copy()
        if self.platform.lower() == "darwin":
            # on osx we assume a musl cross compilation
            # linker installed via `brew install filosottile/musl-cross/musl-cross`
            # This requires the follow env vars when invoking cargo build
            env.update(
                {
                    "RUSTFLAGS": "{rust_flags} -Clinker=x86_64-linux-musl-gcc".format(
                        rust_flags=env.get("RUSTFLAGS", "")
                    ),
                    "TARGET_CC": "x86_64-linux-musl-gcc",
                    "CC_x86_64_unknown_linux_musl": "x86_64-linux-musl-gcc",
                }
            )
        if self.platform.lower() == "windows":
            # on windows we assume a musl cross compilation
            # linker is available via rusts embedded llvm linker "rust-lld"
            # but cc is used as the default
            # source: https://github.com/KodrAus/rust-cross-compile
            # This requires the follow env vars when invoking cargo build
            env.update(
                {
                    "RUSTFLAGS": "{rust_flags} -Clinker=rust-lld".format(rust_flags=env.get("RUSTFLAGS", "")),
                    "TARGET_CC": "rust-lld",
                    "CC_x86_64_unknown_linux_musl": "rust-lld",
                }
            )
        return env

    def execute(self):
        (package, _) = self.resolve_binary(self.cargo_metadata())
        p = self.osutils.popen(
            self.build_command(package),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=self.build_env(),
            cwd=self.source_dir,
        )
        out, err = p.communicate()
        if p.returncode != 0:
            raise BuilderError(message=err.decode("utf8").strip())
        return out.decode("utf8").strip()


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
        (_, binary) = parse_handler(self.handler)
        profile = "debug" if self.mode == BuildMode.DEBUG else "release"
        target = os.path.join(self.source_dir, "target", CARGO_TARGET)
        return os.path.join(target, profile, binary)

    def execute(self):
        self.osutils.makedirs(self.artifacts_dir)
        self.osutils.copyfile(self.binary_path(), os.path.join(self.artifacts_dir, "bootstrap"))
