from unittest import TestCase
from unittest.mock import MagicMock, patch
from parameterized import parameterized
import io
import logging
import os

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.workflows.rust_cargo.actions import (
    CargoLambdaExecutionException,
    RustCargoLambdaBuildAction,
    RustCopyAndRenameAction,
)
from aws_lambda_builders.workflows.rust_cargo.cargo_lambda import SubprocessCargoLambda

LOG = logging.getLogger("aws_lambda_builders.workflows.rust_cargo.cargo_lambda")


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.stderr = io.BytesIO(err)
        self.stdout = [out]
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err

    def wait(self):
        return self.returncode


def fake_metadata_popen():
    # Stands in for `cargo metadata`, which run() calls to resolve the shared
    # target directory before invoking the build.
    metadata = b'{"target_directory": "/source_dir/target", "packages": []}'
    return FakePopen(out=metadata, retcode=0)


class TestBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        # run() first calls `cargo metadata` to resolve the target dir, then the build
        self.osutils.popen.side_effect = [fake_metadata_popen(), FakePopen()]

        def which(cmd, executable_search_paths):
            return ["/bin/cargo-lambda"]

        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)
        self.subprocess_cargo_lambda = proc

    @parameterized.expand(
        [
            ("provided.al2", "x86_64", "x86_64-unknown-linux-gnu.2.26"),
            ("provided.al2", "arm64", "aarch64-unknown-linux-gnu.2.26"),
        ]
    )
    def test_release_build_cargo_command_with_correct_targets(self, runtime, architecture, expected_target):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, None, self.subprocess_cargo_lambda, runtime, architecture
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release", "--target", expected_target],
        )

    def test_release_build_cargo_command_for_provided_al2023(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, None, self.subprocess_cargo_lambda, "provided.al2023"
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release"],
        )

    def test_release_build_cargo_command_without_release_mode(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction("source_dir", {"cargo": cargo}, None, None, self.subprocess_cargo_lambda)
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release"],
        )

    def test_release_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, None, self.subprocess_cargo_lambda
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release"],
        )

    def test_release_build_cargo_command_with_target(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, None, self.subprocess_cargo_lambda, "arm64"
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--release", "--arm64"],
        )

    def test_debug_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.DEBUG, None, self.subprocess_cargo_lambda
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build"],
        )

    def test_debug_build_cargo_command_with_architecture(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.DEBUG, None, self.subprocess_cargo_lambda, "arm64"
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64"],
        )

    def test_debug_build_cargo_command_with_flags(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        flags = ["--package", "package-in-workspace"]
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.DEBUG, None, self.subprocess_cargo_lambda, "arm64", flags=flags
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64", "--package", "package-in-workspace"],
        )

    def test_debug_build_cargo_command_with_handler(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.DEBUG, None, self.subprocess_cargo_lambda, "arm64", handler="foo"
        )
        self.assertEqual(
            action.build_command(),
            ["path/to/cargo", "lambda", "build", "--arm64", "--bin", "foo"],
        )

    def test_execute_happy_path(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, self.subprocess_cargo_lambda, None
        )
        action.execute()

    def test_execute_cargo_build_fail(self):
        popen = FakePopen(retcode=1, err=b"build failed")
        self.subprocess_cargo_lambda._osutils.popen.side_effect = [fake_metadata_popen(), popen]

        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = RustCargoLambdaBuildAction(
            "source_dir", {"cargo": cargo}, BuildMode.RELEASE, self.subprocess_cargo_lambda, None
        )
        with self.assertRaises(ActionFailedError) as err_assert:
            action.execute()
        self.assertEqual(err_assert.exception.args[0], "Cargo Lambda failed: build failed")

    def test_execute_happy_with_logger(self):
        LOG.setLevel(logging.DEBUG)
        with patch.object(LOG, "debug") as mock_warning:
            cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
            action = RustCargoLambdaBuildAction(
                "source_dir", {"cargo": cargo}, BuildMode.RELEASE, self.subprocess_cargo_lambda, None
            )
            out = action.execute()
            self.assertEqual(out, "out")
        mock_warning.assert_any_call("RUST_LOG environment variable set to `%s`", "debug")


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

    def test_copy_path_uses_shared_target_dir_and_resolved_binary(self):
        # Workspace member with no explicit handler: the binary is found in the shared
        # workspace target dir under the bin name cargo reported for this member, even
        # though that directory also holds the other members' binaries.
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        subprocess_cargo_lambda = MagicMock()
        workspace_target = os.path.join(os.sep, "ws_root", "target")
        subprocess_cargo_lambda.resolve_workspace_layout.return_value = {
            "target_directory": workspace_target,
            "binary_name": "member",
        }

        action = RustCopyAndRenameAction(
            os.path.join(os.sep, "ws_root", "member"), "output_dir", None, {"cargo": cargo}, subprocess_cargo_lambda
        )

        self.assertEqual(action.binary_path(), os.path.join(workspace_target, "lambda", "member", "bootstrap"))
        subprocess_cargo_lambda.resolve_workspace_layout.assert_called_with(
            "path/to/cargo", os.path.join(os.sep, "ws_root", "member")
        )

    def test_copy_path_explicit_handler_overrides_resolved_binary(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        subprocess_cargo_lambda = MagicMock()
        workspace_target = os.path.join(os.sep, "ws_root", "target")
        subprocess_cargo_lambda.resolve_workspace_layout.return_value = {
            "target_directory": workspace_target,
            "binary_name": "member",
        }

        action = RustCopyAndRenameAction(
            os.path.join(os.sep, "ws_root", "member"), "output_dir", "foo", {"cargo": cargo}, subprocess_cargo_lambda
        )

        self.assertEqual(action.binary_path(), os.path.join(workspace_target, "lambda", "foo", "bootstrap"))

    def test_copy_path_falls_back_to_source_target_when_layout_unresolved(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        subprocess_cargo_lambda = MagicMock()
        subprocess_cargo_lambda.resolve_workspace_layout.return_value = {
            "target_directory": None,
            "binary_name": None,
        }

        action = RustCopyAndRenameAction("source_dir", "output_dir", "foo", {"cargo": cargo}, subprocess_cargo_lambda)

        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "foo", "bootstrap"))

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.os.listdir")
    def test_binary_path_without_handler_uses_single_binary_dir(self, listdir_mock):
        listdir_mock.return_value = ["only_bin"]
        action = RustCopyAndRenameAction("source_dir", "output_dir")
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "lambda", "only_bin", "bootstrap"))

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.os.listdir")
    def test_binary_path_without_handler_raises_when_ambiguous(self, listdir_mock):
        listdir_mock.return_value = ["bin_a", "bin_b"]
        action = RustCopyAndRenameAction("source_dir", "output_dir")
        with self.assertRaises(CargoLambdaExecutionException) as raised:
            action.binary_path()
        self.assertIn("unable to find function binary", raised.exception.args[0])

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        osutils.copyfile.return_value = ""
        osutils.makedirs.return_value = ""
        action = RustCopyAndRenameAction("source_dir", "foo", "output_dir", osutils=osutils)
        action.execute()
