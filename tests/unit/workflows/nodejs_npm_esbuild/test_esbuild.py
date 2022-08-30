from unittest import TestCase
from mock import patch
from parameterized import parameterized

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild import (
    SubprocessEsbuild,
    EsbuildExecutionError,
    EsbuildCommandBuilder,
)


class FakePopen:
    def __init__(self, out=b"out", err=b"err", retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessEsbuild(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):
        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = "PIPE"
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]

        which = lambda cmd, executable_search_paths: ["{}/{}".format(executable_search_paths[0], cmd)]

        self.under_test = SubprocessEsbuild(self.osutils, ["/a/b", "/c/d"], which)

    def test_run_executes_binary_found_in_exec_paths(self):

        self.under_test.run(["arg-a", "arg-b"])

        self.osutils.popen.assert_called_with(
            ["/a/b/esbuild", "arg-a", "arg-b"], cwd=None, stderr="PIPE", stdout="PIPE"
        )

    def test_uses_cwd_if_supplied(self):
        self.under_test.run(["arg-a", "arg-b"], cwd="/a/cwd")

        self.osutils.popen.assert_called_with(
            ["/a/b/esbuild", "arg-a", "arg-b"], cwd="/a/cwd", stderr="PIPE", stdout="PIPE"
        )

    def test_returns_popen_out_decoded_if_retcode_is_0(self):
        self.popen.out = b"some encoded text\n\n"

        result = self.under_test.run(["pack"])

        self.assertEqual(result, "some encoded text")

    def test_raises_EsbuildExecutionError_with_err_text_if_retcode_is_not_0(self):
        self.popen.returncode = 1
        self.popen.err = b"some error text\n\n"

        with self.assertRaises(EsbuildExecutionError) as raised:
            self.under_test.run(["pack"])

        self.assertEqual(raised.exception.args[0], "Esbuild Failed: some error text")

    def test_raises_EsbuildExecutionError_if_which_returns_no_results(self):

        which = lambda cmd, executable_search_paths: []
        self.under_test = SubprocessEsbuild(self.osutils, ["/a/b", "/c/d"], which)
        with self.assertRaises(EsbuildExecutionError) as raised:
            self.under_test.run(["pack"])

        self.assertEqual(
            raised.exception.args[0],
            "Esbuild Failed: Cannot find esbuild. esbuild must be installed on the host machine to use this feature. "
            "It is recommended to be installed on the PATH, but can also be included as a project dependency.",
        )

    def test_raises_ValueError_if_args_not_a_list(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run(("pack"))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):
        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")


class TestImplicitFileTypeResolution(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild")
    def setUp(self, OSUtilMock, SubprocessEsbuildMock):
        self.osutils = OSUtilMock.return_value
        self.subprocess_esbuild = SubprocessEsbuildMock.return_value
        self.esbuild_command_builder = EsbuildCommandBuilder(
            "source",
            "artifacts",
            {},
            self.osutils,
            "package.json",
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
        explicit_entry_point = self.esbuild_command_builder._get_explicit_file_type(entry_point, "")
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
            self.esbuild_command_builder._get_explicit_file_type(entry_point, "invalid")
        self.assertEqual(str(context.exception), "entry point invalid does not exist")


class TestEsbuildCommandBuilder(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_builds_entry_points(self, osutils_mock):
        bundler_config = {"entry_points": ["x.js", "y.ts"]}
        args = (
            EsbuildCommandBuilder("scratch", "artifacts", bundler_config, osutils_mock, "")
            .build_entry_points()
            .get_command()
        )
        self.assertEqual(args, ["x.js", "y.ts"])

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_builds_default_values(self, osutils_mock):
        bundler_config = {}
        args = (
            EsbuildCommandBuilder("scratch", "artifacts", bundler_config, osutils_mock, "")
            .build_default_values()
            .get_command()
        )
        self.assertEqual(
            args,
            [
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--format=cjs",
                "--minify",
            ],
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_combined_builder_exclude_all_dependencies(self, osutils_mock):
        bundler_config = {"entry_points": ["x.js"], "loader": [".proto=text", ".json=js"]}
        osutils_mock.parse_json.return_value = {
            "dependencies": {"@faker-js/faker": "7.1.0", "uuidv4": "^6.2.12", "axios": "0.0.0"}
        }
        args = (
            EsbuildCommandBuilder("scratch", "artifacts", bundler_config, osutils_mock, "")
            .build_entry_points()
            .build_default_values()
            .build_esbuild_args_from_config()
            .build_with_no_dependencies()
            .get_command()
        )
        self.assertEqual(
            args,
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
                "--external:@faker-js/faker",
                "--external:uuidv4",
                "--external:axios",
            ],
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_builds_args_from_config(self, osutils_mock):
        bundler_config = {
            "minify": True,
            "sourcemap": False,
            "format": "esm",
            "target": "node14",
            "loader": [".proto=text", ".json=js"],
            "external": ["aws-sdk", "axios"],
            "main_fields": "module,main",
        }

        args = (
            EsbuildCommandBuilder("scratch", "artifacts", bundler_config, osutils_mock, "")
            .build_esbuild_args_from_config()
            .get_command()
        )
        self.assertEqual(
            args,
            [
                "--minify",
                "--target=node14",
                "--format=esm",
                "--main-fields=module,main",
                "--external:aws-sdk",
                "--external:axios",
                "--loader:.proto=text",
                "--loader:.json=js",
            ],
        )

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_combined_builder_with_dependencies(self, osutils_mock):
        bundler_config = {"entry_points": ["x.js"], "loader": [".proto=text", ".json=js"], "format": "esm"}
        args = (
            EsbuildCommandBuilder("scratch", "artifacts", bundler_config, osutils_mock, "")
            .build_entry_points()
            .build_default_values()
            .build_esbuild_args_from_config()
            .get_command()
        )
        self.assertEqual(
            args,
            [
                "x.js",
                "--bundle",
                "--platform=node",
                "--outdir=artifacts",
                "--target=es2020",
                "--minify",
                "--format=esm",
                "--loader:.proto=text",
                "--loader:.json=js",
            ],
        )

    @parameterized.expand(
        [
            ("main_fields", "main-fields"),
            ("entry_points", "entry-points"),
            ("main-fields", "main-fields"),
            ("bundle", "bundle"),
        ]
    )
    def test_convert_snake_case_to_kebab_case(self, field, expected):
        self.assertEqual(EsbuildCommandBuilder._convert_snake_to_kebab_case(field), expected)
