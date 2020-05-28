from unittest import TestCase
from mock import patch
import json
import os

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflow import BuildMode
from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.rust_cargo.actions import (
    parse_handler,
    BuildAction,
    CopyAndRenameAction,
    BuilderError,
)


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestBuildAction(TestCase):
    def test_linux_release_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "linux", BuildMode.RELEASE)
        self.assertEqual(action.build_command("foo"), ["path/to/cargo", "build", "-p", "foo", "--release"])

    def test_nonlinux_release_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "darwin", BuildMode.RELEASE)
        self.assertEqual(
            action.build_command("foo"),
            ["path/to/cargo", "build", "-p", "foo", "--release", "--target", "x86_64-unknown-linux-musl"],
        )

    def test_linux_debug_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "linux", BuildMode.DEBUG)
        self.assertEqual(action.build_command("foo"), ["path/to/cargo", "build", "-p", "foo"])

    def test_nonlinux_debug_build_cargo_command(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "darwin", BuildMode.DEBUG)
        self.assertEqual(
            action.build_command("foo"),
            ["path/to/cargo", "build", "-p", "foo", "--target", "x86_64-unknown-linux-musl"],
        )

    def test_parse_handler_simple(self):
        self.assertEqual(parse_handler("foo"), ("foo", "foo"))

    def test_parse_handler_structured(self):
        self.assertEqual(parse_handler("foo.bar"), ("foo", "bar"))

    def test_resolve_returns_bin_handler_exists(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo.bar", {"cargo": cargo}, "darwin", BuildMode.DEBUG)
        self.assertEqual(
            action.resolve_binary({"packages": [{"name": "foo", "targets": [{"kind": ["bin"], "name": "bar"}]}]}),
            ("foo", "bar"),
        )

    def test_resolve_returns_raise_build_error_if_handler_doesnt_exist(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo.bar", {"cargo": cargo}, "darwin", BuildMode.DEBUG)
        with self.assertRaises(BuilderError) as err_assert:
            action.resolve_binary({"packages": [{"name": "foo", "targets": [{"kind": ["bin"], "name": "baz"}]}]})
        self.assertEquals(
            err_assert.exception.args[0], "Builder Failed: Cargo project does not contain a foo.bar binary"
        )

    def test_build_env_on_darwin(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "darwin", BuildMode.RELEASE)
        env = action.build_env()
        self.assertDictContainsSubset(
            {
                "RUSTFLAGS": " -Clinker=x86_64-linux-musl-gcc",
                "TARGET_CC": "x86_64-linux-musl-gcc",
                "CC_x86_64_unknown_linux_musl": "x86_64-linux-musl-gcc",
            },
            env,
        )

    def test_build_env_on_windows(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "windows", BuildMode.RELEASE)
        env = action.build_env()
        self.assertDictContainsSubset(
            {"RUSTFLAGS": " -Clinker=rust-lld", "TARGET_CC": "rust-lld", "CC_x86_64_unknown_linux_musl": "rust-lld",},
            env,
        )

    def test_build_env_on_linux(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "linux", BuildMode.RELEASE)
        env = action.build_env()
        self.assertIsNone(env.get("RUSTFLAGS"))
        self.assertIsNone(env.get("TARGET_CC"))
        self.assertIsNone(env.get("CC_x86_64_unknown_linux_musl"))

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute_happy_path(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        popen1 = FakePopen(
            out=json.dumps({"packages": [{"name": "foo", "targets": [{"kind": ["bin"], "name": "foo"}]}]})
        )
        popen2 = FakePopen()
        osutils.popen.side_effect = [popen1, popen2]
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "darwin", BuildMode.RELEASE, osutils=osutils)
        action.execute()

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute_cargo_meta_fail(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        popen1 = FakePopen(retcode=1, err=b"meta failed")
        popen2 = FakePopen()
        osutils.popen.side_effect = [popen1, popen2]
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "darwin", BuildMode.RELEASE, osutils=osutils)
        with self.assertRaises(BuilderError) as err_assert:
            action.execute()
        self.assertEquals(err_assert.exception.args[0], "Builder Failed: meta failed")

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute_cargo_build_fail(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        popen1 = FakePopen(
            out=json.dumps({"packages": [{"name": "foo", "targets": [{"kind": ["bin"], "name": "foo"}]}]})
        )
        popen2 = FakePopen(retcode=1, err=b"build failed")
        osutils.popen.side_effect = [popen1, popen2]
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = BuildAction("source_dir", "foo", {"cargo": cargo}, "darwin", BuildMode.RELEASE, osutils=osutils)
        with self.assertRaises(BuilderError) as err_assert:
            action.execute()
        self.assertEquals(err_assert.exception.args[0], "Builder Failed: build failed")


class TestCopyAndRenameAction(TestCase):
    def test_debug_copy_path(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = CopyAndRenameAction("source_dir", "foo", "output_dir", "linux", BuildMode.DEBUG)
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "debug", "foo"))

    def test_release_copy_path(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = CopyAndRenameAction("source_dir", "foo", "output_dir", "linux", BuildMode.RELEASE)
        self.assertEqual(action.binary_path(), os.path.join("source_dir", "target", "release", "foo"))

    def test_nonlinux_copy_path(self):
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = CopyAndRenameAction("source_dir", "foo", "output_dir", "darwin", BuildMode.RELEASE)
        self.assertEqual(
            action.binary_path(), os.path.join("source_dir", "target", "x86_64-unknown-linux-musl", "release", "foo")
        )

    @patch("aws_lambda_builders.workflows.rust_cargo.actions.OSUtils")
    def test_execute(self, OSUtilsMock):
        osutils = OSUtilsMock.return_value
        osutils.copyfile.return_value = ""
        osutils.makedirs.return_value = ""
        cargo = BinaryPath(None, None, None, binary_path="path/to/cargo")
        action = CopyAndRenameAction("source_dir", "foo", "output_dir", "darwin", BuildMode.RELEASE, osutils=osutils)
        action.execute()
