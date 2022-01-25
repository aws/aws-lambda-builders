from unittest import TestCase
from mock import patch, call
from parameterized import parameterized

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcAndLockfileCopyAction,
    NodejsNpmrcCleanUpAction,
    NodejsNpmLockFileCleanUpAction,
    NodejsNpmCIAction,
    EsbuildBundleAction,
)
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError


class TestNodejsNpmPackAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmPackAction(
            "artifacts", "scratch_dir", "manifest", osutils=osutils, subprocess_npm=subprocess_npm
        )

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        subprocess_npm.run.return_value = "package.tar"

        action.execute()

        subprocess_npm.run.assert_called_with(["pack", "-q", "file:/abs:/dir:manifest"], cwd="scratch_dir")
        osutils.extract_tarfile.assert_called_with("scratch_dir/package.tar", "artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmPackAction(
            "artifacts", "scratch_dir", "manifest", osutils=osutils, subprocess_npm=subprocess_npm
        )

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmInstallAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_installs_npm_production_dependencies_for_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("artifacts", subprocess_npm=subprocess_npm)

        action.execute()

        expected_args = ["install", "-q", "--no-audit", "--no-save", "--production", "--unsafe-perm"]

        subprocess_npm.run.assert_called_with(expected_args, cwd="artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_can_set_mode(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("artifacts", subprocess_npm=subprocess_npm, is_production=False)

        action.execute()

        expected_args = ["install", "-q", "--no-audit", "--no-save", "--production=false", "--unsafe-perm"]

        subprocess_npm.run.assert_called_with(expected_args, cwd="artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmInstallAction("artifacts", subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmCIAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmCIAction("sources", subprocess_npm=subprocess_npm)

        action.execute()

        subprocess_npm.run.assert_called_with(["ci"], cwd="sources")

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmCIAction("sources", subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmrcAndLockfileCopyAction(TestCase):
    @parameterized.expand(
        [
            [False, False],
            [True, False],
            [False, True],
            [True, True],
        ]
    )
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_copies_into_a_project_if_file_exists(self, npmrc_exists, package_lock_exists, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcAndLockfileCopyAction("artifacts", "source", osutils=osutils)
        osutils.file_exists.side_effect = [npmrc_exists, package_lock_exists]
        action.execute()

        filename_exists = {
            ".npmrc": npmrc_exists,
            "package-lock.json": package_lock_exists,
        }
        file_exists_calls = [call("source/{}".format(filename)) for filename in filename_exists]
        copy_file_calls = [
            call("source/{}".format(filename), "artifacts") for filename, exists in filename_exists.items() if exists
        ]
        osutils.file_exists.assert_has_calls(file_exists_calls)
        osutils.copy_file.assert_has_calls(copy_file_calls)

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_copying_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.copy_file.side_effect = OSError()

        action = NodejsNpmrcAndLockfileCopyAction("artifacts", "source", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmrcCleanUpAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_npmrc_if_npmrc_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/.npmrc")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_npmrc_removal_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_removing_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.remove_file.side_effect = OSError()

        action = NodejsNpmrcCleanUpAction("artifacts", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmLockFileCleanUpAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_dot_package_lock_if_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b, c: "{}/{}/{}".format(a, b, c)

        action = NodejsNpmLockFileCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/node_modules/.package-lock.json")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_lockfile_removal_if_it_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b, c: "{}/{}/{}".format(a, b, c)

        action = NodejsNpmLockFileCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_removing_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b, c: "{}/{}/{}".format(a, b, c)

        osutils.remove_file.side_effect = OSError()

        action = NodejsNpmLockFileCleanUpAction("artifacts", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestEsbuildBundleAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.esbuild.SubprocessEsbuild")
    def setUp(self, OSUtilMock, SubprocessEsbuildMock):
        self.osutils = OSUtilMock.return_value
        self.subprocess_esbuild = SubprocessEsbuildMock.return_value
        self.osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)
        self.osutils.file_exists.side_effect = [True, True]

    def test_raises_error_if_entrypoints_not_specified(self):
        action = EsbuildBundleAction("source", "artifacts", {"config": "param"}, self.osutils, self.subprocess_esbuild)
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "entry_points not set ({'config': 'param'})")

    def test_raises_error_if_entrypoints_not_a_list(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"config": "param", "entry_points": "abc"}, self.osutils, self.subprocess_esbuild
        )
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(
            raised.exception.args[0], "entry_points must be a list ({'config': 'param', 'entry_points': 'abc'})"
        )

    def test_raises_error_if_entrypoints_empty_list(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"config": "param", "entry_points": []}, self.osutils, self.subprocess_esbuild
        )
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(
            raised.exception.args[0], "entry_points must not be empty ({'config': 'param', 'entry_points': []})"
        )

    def test_packages_javascript_with_minification_and_sourcemap(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js"]}, self.osutils, self.subprocess_esbuild
        )
        action.execute()

        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--format=cjs",
                "--minify",
                "--sourcemap",
                "--target=es2020",
                "--outdir=artifacts",
            ],
            cwd="source",
        )

    def test_checks_if_single_entrypoint_exists(self):

        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js"]}, self.osutils, self.subprocess_esbuild
        )
        self.osutils.file_exists.side_effect = [False]

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.osutils.file_exists.assert_called_with("source/x.js")

        self.assertEqual(raised.exception.args[0], "entry point source/x.js does not exist")

    def test_checks_if_multiple_entrypoints_exist(self):

        self.osutils.file_exists.side_effect = [True, False]
        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js", "y.js"]}, self.osutils, self.subprocess_esbuild
        )

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.osutils.file_exists.assert_any_call("source/x.js")

        self.osutils.file_exists.assert_called_with("source/y.js")

        self.assertEqual(raised.exception.args[0], "entry point source/y.js does not exist")

    def test_excludes_sourcemap_if_requested(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js"], "sourcemap": False}, self.osutils, self.subprocess_esbuild
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--format=cjs",
                "--minify",
                "--target=es2020",
                "--outdir=artifacts",
            ],
            cwd="source",
        )

    def test_does_not_minify_if_requested(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js"], "minify": False}, self.osutils, self.subprocess_esbuild
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--format=cjs",
                "--sourcemap",
                "--target=es2020",
                "--outdir=artifacts",
            ],
            cwd="source",
        )

    def test_uses_specified_target(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js"], "target": "node14"}, self.osutils, self.subprocess_esbuild
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--format=cjs",
                "--minify",
                "--sourcemap",
                "--target=node14",
                "--outdir=artifacts",
            ],
            cwd="source",
        )

    def test_includes_multiple_entry_points_if_requested(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js", "y.js"], "target": "node14"},
            self.osutils,
            self.subprocess_esbuild,
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "y.js",
                "--bundle",
                "--platform=node",
                "--format=cjs",
                "--minify",
                "--sourcemap",
                "--target=node14",
                "--outdir=artifacts",
            ],
            cwd="source",
        )
