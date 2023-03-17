from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.actions import (
    EsbuildBundleAction,
    check_minimum_esbuild_version,
    MINIMUM_VERSION_FOR_EXTERNAL,
)


class TestEsbuildBundleAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
    def setUp(self, OSUtilMock, SubprocessEsbuildMock):
        self.osutils = OSUtilMock.return_value
        self.subprocess_esbuild = SubprocessEsbuildMock.return_value
        self.subprocess_esbuild.run.return_value = MINIMUM_VERSION_FOR_EXTERNAL
        self.osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)
        self.osutils.file_exists.side_effect = [True, True]

    def test_raises_error_if_entrypoints_not_specified(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"config": "param"}, self.osutils, self.subprocess_esbuild, "package.json"
        )
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "entry_points not set ({'config': 'param'})")

    def test_raises_error_if_entrypoints_not_a_list(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"config": "param", "entry_points": "abc"},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(
            raised.exception.args[0], "entry_points must be a list ({'config': 'param', 'entry_points': 'abc'})"
        )

    def test_raises_error_if_entrypoints_empty_list(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"config": "param", "entry_points": []},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )
        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(
            raised.exception.args[0], "entry_points must not be empty ({'config': 'param', 'entry_points': []})"
        )

    def test_packages_javascript_with_minification_and_sourcemap(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"], "sourcemap": True},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )
        action.execute()

        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--format=cjs",
                "--minify",
                "--sourcemap",
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
            "",
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--format=cjs",
                "--minify",
                "--external:fetch",
                "--external:aws-sdk",
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
            "",
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--format=cjs",
                "--minify",
                "--loader:.proto=text",
                "--loader:.json=js",
            ],
            cwd="source",
        )

    def test_checks_if_single_entrypoint_exists(self):
        action = EsbuildBundleAction(
            "source", "artifacts", {"entry_points": ["x.js"]}, self.osutils, self.subprocess_esbuild, "package.json"
        )
        self.osutils.file_exists.side_effect = [False]

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.osutils.file_exists.assert_called_with("source/x.js")

        self.assertEqual(raised.exception.args[0], "entry point source/x.js does not exist")

    def test_checks_if_multiple_entrypoints_exist(self):
        self.osutils.file_exists.side_effect = [True, False]
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js", "y.js"]},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.osutils.file_exists.assert_any_call("source/x.js")

        self.osutils.file_exists.assert_called_with("source/y.js")

        self.assertEqual(raised.exception.args[0], "entry point source/y.js does not exist")

    def test_excludes_sourcemap_if_requested(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"], "sourcemap": False},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--format=cjs",
                "--minify",
            ],
            cwd="source",
        )

    def test_does_not_minify_if_requested(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"], "minify": False},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--format=cjs",
            ],
            cwd="source",
        )

    def test_uses_specified_target(self):
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"], "target": "node14"},
            self.osutils,
            self.subprocess_esbuild,
            "package.json",
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--format=cjs",
                "--minify",
                "--target=node14",
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
            "package.json",
        )
        action.execute()
        self.subprocess_esbuild.run.assert_called_with(
            [
                "x.js",
                "y.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--format=cjs",
                "--minify",
                "--target=node14",
            ],
            cwd="source",
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_includes_building_with_external_dependencies(self, osutils_mock):
        osutils_mock.parse_json.return_value = {
            "dependencies": {"@faker-js/faker": "7.1.0", "uuidv4": "^6.2.12", "axios": "0.0.0"}
        }
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js", "y.js"], "target": "node14", "external": "./node_modules/*"},
            osutils_mock,
            self.subprocess_esbuild,
            "package.json",
        )
        action.execute()
        self.assertNotIn("external", action._bundler_config)
        self.subprocess_esbuild.run.assert_called_with(
            [
                "--external:@faker-js/faker",
                "--external:uuidv4",
                "--external:axios",
                "x.js",
                "y.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--format=cjs",
                "--minify",
                "--target=node14",
            ],
            cwd="source",
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
    def test_building_with_external_dependencies_in_bundler_config_fails_if_esbuild_version_less_than_minimum(
        self, osutils_mock, subprocess_esbuild_mock
    ):
        subprocess_esbuild_mock.run.return_value = "0.14.12"
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js", "y.js"], "target": "node14", "external": "./node_modules/*"},
            osutils_mock,
            subprocess_esbuild_mock,
            "package.json",
        )
        with self.assertRaises(ActionFailedError):
            action.execute()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
    def test_building_with_skip_deps_fails_if_esbuild_version_less_than_minimum(
        self, osutils_mock, subprocess_esbuild_mock
    ):
        subprocess_esbuild_mock.run.return_value = "0.14.12"
        action = EsbuildBundleAction(
            "source",
            "artifacts",
            {"entry_points": ["x.js"]},
            osutils_mock,
            subprocess_esbuild_mock,
            "package.json",
            True,
        )
        with self.assertRaises(ActionFailedError):
            action.execute()


class TestEsbuildVersionChecker(TestCase):
    @parameterized.expand(["0.14.0", "0.0.0", "0.14.12"])
    def test_outdated_esbuild_versions(self, version):
        subprocess_esbuild = Mock()
        subprocess_esbuild.run.return_value = version
        with self.assertRaises(ActionFailedError) as content:
            check_minimum_esbuild_version(
                minimum_version_required="0.14.13", working_directory="scratch", subprocess_esbuild=subprocess_esbuild
            )
        self.assertEqual(
            str(content.exception),
            f"Unsupported esbuild version. To use a dependency layer, the esbuild version "
            f"must be at least 0.14.13. Version found: {version}",
        )

    @parameterized.expand(["a.0.0", "a.b.c"])
    def test_invalid_esbuild_versions(self, version):
        subprocess_esbuild = Mock()
        subprocess_esbuild.run.return_value = version
        with self.assertRaises(ActionFailedError) as content:
            check_minimum_esbuild_version(
                minimum_version_required="0.14.13", working_directory="scratch", subprocess_esbuild=subprocess_esbuild
            )
        self.assertEqual(
            str(content.exception), "Unable to parse esbuild version: invalid literal for int() with base 10: 'a'"
        )

    @parameterized.expand(["0.14.13", "1.0.0", "10.0.10"])
    def test_valid_esbuild_versions(self, version):
        subprocess_esbuild = Mock()
        subprocess_esbuild.run.return_value = version
        try:
            check_minimum_esbuild_version(
                minimum_version_required="0.14.13", working_directory="scratch", subprocess_esbuild=subprocess_esbuild
            )
        except ActionFailedError:
            self.fail("Encountered an unexpected exception.")
