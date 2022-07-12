from unittest import TestCase
from mock import patch
import json
import os

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.rust_cargo.actions import (
    RustBuildAction,
    RustCopyAndRenameAction,
)


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestBuildAction(TestCase):
    def test_release_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustBuildAction("source_dir", {"cargo": cargo}, BuildMode.RELEASE)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release"],
        )

    def test_release_build_cargo_command_with_target(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustBuildAction("source_dir", {"cargo": cargo}, BuildMode.RELEASE, "arm64")
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release", "--arm64"],
        )

    def test_debug_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build"],
        )

    def test_debug_build_cargo_command_with_target(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG, "arm64")
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64"],
        )

    def test_debug_build_cargo_command_with_target(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        flags = ["--package", "package-in-workspace"]
        action = RustBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG, "arm64", flags=flags)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64", "--package", "package-in-workspace"],
        )

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute_happy_path(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        popen = FakePopen()
        osutils.popen.side_effect = [popen]
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, osutils=osutils
        )
        action.execute()

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute_cargo_build_fail(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        popen = FakePopen(retcode=1, err=b"build failed")
        osutils.popen.side_effect = [popen]
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, osutils=osutils
        )
        with self.assertRaises(ActionFailedError) as err_assert:
            action.execute()
        self.assertEqual(err_assert.exception.args[0], "Builder Failed: build failed")


class TestCopyAndRenameAction(TestCase):
    def test_debug_copy_path(self):
        action = RustCopyAndRenameAction("source_dir", "foo", "output_dir")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    def test_release_copy_path(self):
        action = RustCopyAndRenameAction("source_dir", "foo", "output_dir")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    def test_nonlinux_copy_path(self):
        action = RustCopyAndRenameAction("source_dir", "foo", "output_dir")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        osutils.copyfile.return_value = ""
        osutils.makedirs.return_value = ""
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCopyAndRenameAction(
            "source_dir", "foo", "output_dir", osutils=osutils
        )
        action.execute()
