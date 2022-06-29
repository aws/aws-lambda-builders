import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

from mock import patch
from parameterized import parameterized

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.actions import EsbuildBundleAction, EsbuildCheckVersionAction


class TestEsbuildBundleAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.node.SubprocessNodejs")
    def setUp(self, OSUtilMock, SubprocessEsbuildMock, SubprocessNodejsMock):
        self.osutils = OSUtilMock.return_value
        self.subprocess_esbuild = SubprocessEsbuildMock.return_value
        self.subprocess_nodejs = SubprocessNodejsMock.return_value
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

    def test_packages_with_externals(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"], "external": ["fetch", "aws-sdk"]},
            self.osutils,
            self.subprocess_esbuild,
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
                "--external:fetch",
                "--external:aws-sdk",
                "--target=es2020",
                "--outdir=artifacts",
            ],
            cwd="source",
        )

    def test_packages_with_custom_loaders(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"], "loader": [".proto=text", ".json=js"]},
            self.osutils,
            self.subprocess_esbuild,
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
                "--loader:.proto=text",
                "--loader:.json=js",
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

    def test_runs_node_subprocess_if_deps_skipped(self):
        action = EsbuildBundleAction(
            tempfile.mkdtemp(),
            "artifacts",
            {"entry_points": ["app.ts"]},
            self.osutils,
            self.subprocess_esbuild,
            self.subprocess_nodejs,
            True,
        )
        action.execute()
        self.subprocess_nodejs.run.assert_called()

    def test_reads_nodejs_bundle_template_file(self):
        template = EsbuildBundleAction._get_node_esbuild_template(["app.ts"], "es2020", "outdir", False, True)
        expected_template = """let skipBundleNodeModules = {
  name: 'make-all-packages-external',
  setup(build) {
    let filter = /^[^.\/]|^\.[^.\/]|^\.\.[^\/]/ // Must not start with "/" or "./" or "../"
    build.onResolve({ filter }, args => ({ path: args.path, external: true }))
  },
}

require('esbuild').build({
  entryPoints: ['app.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  target: 'es2020',
  sourcemap: true,
  outdir: 'outdir',
  minify: false,
  plugins: [skipBundleNodeModules],
}).catch(() => process.exit(1))
"""
        self.assertEqual(template, expected_template)


class TestImplicitFileTypeResolution(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
    def setUp(self, OSUtilMock, SubprocessEsbuildMock):
        self.osutils = OSUtilMock.return_value
        self.subprocess_esbuild = SubprocessEsbuildMock.return_value
        self.action = EsbuildBundleAction(
            "source",
            "artifacts",
            {},
            self.osutils,
            self.subprocess_esbuild,
        )

    @parameterized.expand(
        [
            ([True], "file.ts", "file.ts"),
            ([False, True], "file", "file.js"),
            ([True], "file", "file.ts"),
        ]
    )
    def test_implicit_and_explicit_file_types(self, file_exists, entry_point, expected):
        self.osutils.file_exists.side_effect = file_exists
        explicit_entry_point = self.action._get_explicit_file_type(entry_point, "")
        self.assertEqual(expected, explicit_entry_point)

    @parameterized.expand(
        [
            ([False], "file.ts"),
            ([False, False], "file"),
        ]
    )
    def test_throws_exception_entry_point_not_found(self, file_exists, entry_point):
        self.osutils.file_exists.side_effect = file_exists
        with self.assertRaises(ActionFailedError) as context:
            self.action._get_explicit_file_type(entry_point, "invalid")
        self.assertEqual(str(context.exception), "entry point invalid does not exist")


class TestEsbuildVersionCheckerAction(TestCase):
    @parameterized.expand(["0.14.0", "0.0.0", "0.14.12"])
    def test_outdated_esbuild_versions(self, version):
        subprocess_esbuild = Mock()
        subprocess_esbuild.run.return_value = version
        action = EsbuildCheckVersionAction("scratch", subprocess_esbuild)
        with self.assertRaises(ActionFailedError) as content:
            action.execute()
        self.assertEqual(
            str(content.exception),
            f"Unsupported esbuild version. To use a dependency layer, the esbuild version "
            f"must be at least 0.14.13. Version found: {version}",
        )

    @parameterized.expand(["a.0.0", "a.b.c"])
    def test_invalid_esbuild_versions(self, version):
        subprocess_esbuild = Mock()
        subprocess_esbuild.run.return_value = version
        action = EsbuildCheckVersionAction("scratch", subprocess_esbuild)
        with self.assertRaises(ActionFailedError) as content:
            action.execute()
        self.assertEqual(
            str(content.exception), "Unable to parse esbuild version: invalid literal for int() with base 10: 'a'"
        )

    @parameterized.expand(["0.14.13", "1.0.0", "10.0.10"])
    def test_valid_esbuild_versions(self, version):
        subprocess_esbuild = Mock()
        subprocess_esbuild.run.return_value = version
        action = EsbuildCheckVersionAction("scratch", subprocess_esbuild)
        try:
            action.execute()
        except ActionFailedError:
            self.fail("Encountered an unexpected exception.")
