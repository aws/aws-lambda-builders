from unittest import TestCase
from mock import patch
import logging
import os

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.workflows.rust_cargo.actions import (
    RustCargoLambdaBuildAction,
    RustCopyAndRenameAction,
)
from aws_lambda_builders.workflows.rust_cargo.cargo_lambda import SubprocessCargoLambda
from aws_lambda_builders.workflows.rust_cargo.exceptions import CargoLambdaExecutionException

LOG = logging.getLogger("aws_lambda_builders.workflows.rust_cargo.cargo_lambda")


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.popen.side_effect = [FakePopen()]

        def which(cmd, executable_search_paths):
            return ["/bin/cargo-lambda"]

        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)
        self.subprocess_cargo_lambda = proc

    def test_release_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, BuildMode.RELEASE)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release"],
        )

    def test_release_build_cargo_command_with_target(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, BuildMode.RELEASE, "arm64")
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release", "--arm64"],
        )

    def test_debug_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build"],
        )

    def test_debug_build_cargo_command_with_architecture(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG, "arm64")
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64"],
        )

    def test_debug_build_cargo_command_with_flags(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        flags = ["--package", "package-in-workspace"]
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG, "arm64", flags=flags)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64", "--package", "package-in-workspace"],
        )

    def test_debug_build_cargo_command_with_handler(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, BuildMode.DEBUG, "arm64", handler="foo")
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64", "--bin", "foo"],
        )

    def test_execute_happy_path(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, subprocess_cargo_lambda=self.subprocess_cargo_lambda
        )
        action.execute()

    def test_execute_cargo_build_fail(self):
        popen = FakePopen(retcode=1, err=b"build failed")
        self.subprocess_cargo_lambda._osutils.popen.side_effect = [popen]

        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, subprocess_cargo_lambda=self.subprocess_cargo_lambda
        )
        with self.assertRaises(CargoLambdaExecutionException) as err_assert:
            action.execute()
        self.assertEqual(err_assert.exception.args[0], "Cargo Lambda failed: build failed")

    def test_execute_happy_with_logger(self):
        LOG.setLevel(logging.DEBUG)
        with patch.object(LOG, "debug") as mock_warning:
            cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
            action = RustCargoLambdaBuildAction(
                "source_dir", {"cargo": cargo}, BuildMode.RELEASE, subprocess_cargo_lambda=self.subprocess_cargo_lambda
            )
            out = action.execute()
            self.assertEqual(out, "out")
        mock_warning.assert_called_with("RUST_LOG environment variable set to `%s`", "debug")


class TestCopyAndRenameAction(TestCase):
    def test_debug_copy_path(self):
        action = RustCopyAndRenameAction("source_dir", "output_dir", "foo")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    def test_release_copy_path(self):
        action = RustCopyAndRenameAction("source_dir", "output_dir", "foo")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    def test_nonlinux_copy_path(self):
        action = RustCopyAndRenameAction("source_dir", "output_dir", "foo")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        osutils.copyfile.return_value = ""
        osutils.makedirs.return_value = ""
        action = RustCopyAndRenameAction("source_dir", "foo", "output_dir", osutils=osutils)
        action.execute()
