from json import dumps
from mock import patch
from os.path import basename, normpath
from unittest import TestCase
from re import match

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.actions import (
    NodejsNpmPackAction,
    NodejsNpmInstallAction,
    NodejsNpmrcCopyAction,
    NodejsCleanUpAction,
)
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError


class MockOpener:
    calls = -1

    @property
    def content(self):
        return self._contents[min(self.calls, len(self._contents) - 1)]

    def __init__(self, contents=None):
        if contents is None:
            self._contents = ["{}"]
        else:
            self._contents = contents

    def open(self, filename, mode="r"):
        self.calls += 1
        return FakeFileObject(filename, mode, self.content)


class FakeFileObject(object):
    def __init__(self, filename, mode="r", content="{}"):
        self.filename = filename
        self.mode = mode

        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def read(self):
        if self.mode.startswith("r"):
            return self.content
        elif (self.mode.startswith == "w" or self.mode.startswith == "a") and self.mode.endswith("+"):
            return ""
        else:
            raise IOError("file not open for reading")

    def write(self, data):
        if self.mode.startswith("w") or self.mode.startswith("a") or self.mode.endswith("+"):
            return self.content
        else:
            raise IOError("file not open for writing")


class RegexMatch:
    expressions = []

    def __init__(self, expressions):
        self.expressions = expressions

    def __repr__(self):
        return str(self.expressions)

    def __eq__(self, b):
        _b = b if isinstance(b, list) else [b]

        if len(self.expressions) != len(_b):
            return False

        return all([(match(self.expressions[inx], _b[inx]) is not None) for inx in range(len(self.expressions))])


class TestNodejsNpmPackAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmPackAction(
            "artifacts", "scratch_dir", "manifest", osutils=osutils, subprocess_npm=subprocess_npm
        )

        osutils.normpath.side_effect = lambda value: normpath(value)
        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        osutils.filename.side_effect = lambda path: basename(path)
        osutils.open_file.side_effect = MockOpener().open

        subprocess_npm.run.return_value = "package.tar"

        action.execute()

        subprocess_npm.run.assert_called_with(RegexMatch(["pack", "-q", r"scratch_dir/\d+?/package$"]), cwd="scratch_dir")
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

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_local_dependencies(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmPackAction(
            "artifacts", "scratch_dir", "manifest", osutils=osutils, subprocess_npm=subprocess_npm
        )

        file_open_responses = [
            dumps({"dependencies": {"dep_1": "file:./local/path"}}),
            dumps({"dependencies": {"dep_2": "file:local/path"}}),
            "{}",
        ]

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        osutils.filename.side_effect = lambda path: basename(path)
        osutils.open_file.side_effect = MockOpener(file_open_responses).open

        subprocess_npm.run.return_value = "package.tar"

        action.execute()

        # pack is called once for top level package, then twice for each local dependency
        self.assertEqual(subprocess_npm.run.call_count, 2)
        subprocess_npm.run.assert_any_call(RegexMatch(["pack", "-q", r"scratch_dir/\d+?/package$"]), cwd="scratch_dir")


class TestNodejsNpmInstallAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("artifacts", subprocess_npm=subprocess_npm)

        action.execute()

        expected_args = ["install", "-q", "--no-audit", "--no-save", "--production", "--unsafe-perm"]

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


class TestNodejsNpmrcCopyAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_copies_npmrc_into_a_project(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCopyAction("artifacts", "source", osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.file_exists.assert_called_with("source/.npmrc")
        osutils.copy_file.assert_called_with("source/.npmrc", "artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_copying_npmrc_into_a_project_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCopyAction("artifacts", "source", osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.file_exists.assert_called_with("source/.npmrc")
        osutils.copy_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_copying_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.copy_file.side_effect = OSError()

        action = NodejsNpmrcCopyAction("artifacts", "source", osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsCleanUpAction(TestCase):
    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_npmrc_if_npmrc_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/.npmrc")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_npmrc_removal_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsCleanUpAction("artifacts", osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()
