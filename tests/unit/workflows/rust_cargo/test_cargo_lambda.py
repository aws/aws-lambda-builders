import io
import json
import logging
import os

from unittest import TestCase
from unittest.mock import MagicMock, patch

from aws_lambda_builders.workflows.rust_cargo.actions import CargoLambdaExecutionException
from aws_lambda_builders.workflows.rust_cargo.cargo_lambda import SubprocessCargoLambda


def which(cmd, executable_search_paths):
    return ["/bin/cargo-lambda"]


def metadata_json(target_directory, packages):
    return json.dumps({"target_directory": target_directory, "packages": packages}).encode("utf-8")


def package(name, manifest_path, bins):
    return {
        "name": name,
        "manifest_path": manifest_path,
        "targets": [{"name": bin_name, "kind": ["bin"]} for bin_name in bins],
    }


class TestSubprocessCargoLambda(TestCase):
    def test_raises_RustCargoLambdaBuilderError_if_which_returns_no_results(self):
        def which(cmd, executable_search_paths):
            return []

        proc = SubprocessCargoLambda(which=which)

        with self.assertRaises(CargoLambdaExecutionException) as raised:
            proc.run("cargo lambda build", "/source_dir")

        self.assertEqual(
            raised.exception.args[0],
            "Cargo Lambda failed: Cannot find Cargo Lambda. Cargo Lambda must be installed on the host machine to use this feature. "
            "Follow the gettings started guide to learn how to install it: https://www.cargo-lambda.info/guide/getting-started.html",
        )


class TestResolveWorkspaceLayout(TestCase):
    def setUp(self):
        self.osutils = MagicMock()

    def _metadata_process(self, stdout=b"", stderr=b"", returncode=0):
        process = MagicMock()
        process.communicate.return_value = (stdout, stderr)
        process.returncode = returncode
        return process

    def test_resolves_shared_target_dir_and_member_binary(self):
        member_manifest = os.path.join(os.sep, "ws", "root", "member", "Cargo.toml")
        other_manifest = os.path.join(os.sep, "ws", "root", "other", "Cargo.toml")
        stdout = metadata_json(
            os.path.join(os.sep, "ws", "root", "target"),
            [package("member", member_manifest, ["member"]), package("other", other_manifest, ["other"])],
        )
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "ws", "root", "member"))

        self.assertEqual(layout["target_directory"], os.path.join(os.sep, "ws", "root", "target"))
        self.assertEqual(layout["binary_name"], "member")
        self.osutils.popen.assert_called_once()
        args, kwargs = self.osutils.popen.call_args
        self.assertEqual(args[0], ["/bin/cargo", "metadata", "--no-deps", "--format-version", "1"])
        self.assertEqual(kwargs["cwd"], os.path.join(os.sep, "ws", "root", "member"))

    def test_resolves_binary_when_source_dir_is_relative(self):
        # cargo metadata always reports absolute manifest paths; a caller may still
        # pass a relative source_dir. Both sides must be resolved to absolute paths
        # or the member never matches and binary_name is silently None.
        relative_source_dir = os.path.join("functions", "member")
        absolute_manifest = os.path.realpath(os.path.join(relative_source_dir, "Cargo.toml"))
        stdout = metadata_json(os.path.join(os.sep, "ws", "target"), [package("member", absolute_manifest, ["member"])])
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", relative_source_dir)

        self.assertEqual(layout["binary_name"], "member")

    def test_caches_resolution_per_source_dir(self):
        manifest = os.path.join(os.sep, "proj", "Cargo.toml")
        stdout = metadata_json(os.path.join(os.sep, "proj", "target"), [package("proj", manifest, ["proj"])])
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        first = proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "proj"))
        second = proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "proj"))

        self.assertEqual(first, second)
        self.osutils.popen.assert_called_once()

    def test_binary_name_none_when_member_has_multiple_bins(self):
        manifest = os.path.join(os.sep, "proj", "Cargo.toml")
        stdout = metadata_json(os.path.join(os.sep, "proj", "target"), [package("proj", manifest, ["a", "b"])])
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "proj"))

        self.assertEqual(layout["target_directory"], os.path.join(os.sep, "proj", "target"))
        self.assertIsNone(layout["binary_name"])

    def test_binary_name_none_when_no_member_matches(self):
        other_manifest = os.path.join(os.sep, "elsewhere", "Cargo.toml")
        stdout = metadata_json(os.path.join(os.sep, "ws", "target"), [package("other", other_manifest, ["other"])])
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "ws", "member"))

        self.assertIsNone(layout["binary_name"])

    def test_falls_back_when_metadata_fails(self):
        self.osutils.popen.return_value = self._metadata_process(stderr=b"not a cargo project", returncode=101)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", "/some/dir")

        self.assertEqual(layout, {"target_directory": None, "binary_name": None})

    def test_falls_back_when_metadata_output_invalid_json(self):
        self.osutils.popen.return_value = self._metadata_process(stdout=b"not json")
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", "/some/dir")

        self.assertEqual(layout, {"target_directory": None, "binary_name": None})

    def test_falls_back_when_popen_raises(self):
        self.osutils.popen.side_effect = OSError("cargo not found")
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        layout = proc.resolve_workspace_layout("/bin/cargo", "/some/dir")

        self.assertEqual(layout, {"target_directory": None, "binary_name": None})

    def test_warns_when_workspace_members_share_a_bin_name(self):
        alpha_manifest = os.path.join(os.sep, "ws", "alpha", "Cargo.toml")
        beta_manifest = os.path.join(os.sep, "ws", "beta", "Cargo.toml")
        stdout = metadata_json(
            os.path.join(os.sep, "ws", "target"),
            [package("alpha", alpha_manifest, ["bootstrap"]), package("beta", beta_manifest, ["bootstrap"])],
        )
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        with self.assertLogs("aws_lambda_builders.workflows.rust_cargo.cargo_lambda", level="WARNING") as logs:
            proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "ws", "alpha"))

        self.assertTrue(any("bin named 'bootstrap'" in message for message in logs.output))
        self.assertTrue(any("alpha" in message and "beta" in message for message in logs.output))

    def test_does_not_warn_when_bin_names_are_unique(self):
        alpha_manifest = os.path.join(os.sep, "ws", "alpha", "Cargo.toml")
        beta_manifest = os.path.join(os.sep, "ws", "beta", "Cargo.toml")
        stdout = metadata_json(
            os.path.join(os.sep, "ws", "target"),
            [package("alpha", alpha_manifest, ["alpha"]), package("beta", beta_manifest, ["beta"])],
        )
        self.osutils.popen.return_value = self._metadata_process(stdout=stdout)
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        logger = logging.getLogger("aws_lambda_builders.workflows.rust_cargo.cargo_lambda")
        with patch.object(logger, "warning") as mock_warning:
            proc.resolve_workspace_layout("/bin/cargo", os.path.join(os.sep, "ws", "alpha"))

        mock_warning.assert_not_called()


class TestRunTargetDir(TestCase):
    def setUp(self):
        self.osutils = MagicMock()

    def _metadata_process(self, stdout=b"", stderr=b"", returncode=0):
        process = MagicMock()
        process.communicate.return_value = (stdout, stderr)
        process.returncode = returncode
        return process

    def _build_process(self):
        process = MagicMock()
        process.stdout = [b"built"]
        process.stderr = io.BytesIO(b"")
        process.wait.return_value = 0
        return process

    def _target_dir_passed_to_build(self):
        # The build is the second popen call (the first is `cargo metadata`).
        build_call = self.osutils.popen.call_args_list[-1]
        return build_call.kwargs["env"]["CARGO_TARGET_DIR"]

    def test_run_uses_resolved_shared_target_dir(self):
        manifest = os.path.join(os.sep, "ws", "member", "Cargo.toml")
        stdout = metadata_json(os.path.join(os.sep, "ws", "target"), [package("member", manifest, ["member"])])
        self.osutils.popen.side_effect = [self._metadata_process(stdout=stdout), self._build_process()]
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CARGO_TARGET_DIR", None)
            proc.run(["/bin/cargo", "lambda", "build"], os.path.join(os.sep, "ws", "member"))

        self.assertEqual(self._target_dir_passed_to_build(), os.path.join(os.sep, "ws", "target"))

    def test_run_falls_back_to_relative_target_when_metadata_unavailable(self):
        # When cargo metadata fails, the build must still target the relative "target"
        # dir the workflow used before this change, so the copy step (which falls back
        # the same way) finds the binary.
        self.osutils.popen.side_effect = [
            self._metadata_process(stderr=b"boom", returncode=101),
            self._build_process(),
        ]
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CARGO_TARGET_DIR", None)
            proc.run(["/bin/cargo", "lambda", "build"], os.path.join(os.sep, "ws", "member"))

        self.assertEqual(self._target_dir_passed_to_build(), "target")

    def test_run_preserves_explicit_env_target_dir(self):
        self.osutils.popen.side_effect = [self._build_process()]
        proc = SubprocessCargoLambda(which=which, osutils=self.osutils)

        with patch.dict(os.environ, {"CARGO_TARGET_DIR": "/explicit/target"}):
            proc.run(["/bin/cargo", "lambda", "build"], os.path.join(os.sep, "ws", "member"))

        # metadata is never consulted; the single popen call is the build itself
        self.osutils.popen.assert_called_once()
        self.assertEqual(self._target_dir_passed_to_build(), "/explicit/target")
