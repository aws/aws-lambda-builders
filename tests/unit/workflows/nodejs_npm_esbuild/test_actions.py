from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.actions import EsbuildBundleAction


class TestEsbuildBundleAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
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
