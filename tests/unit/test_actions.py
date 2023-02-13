from pathlib import Path
from unittest import TestCase
from unittest.mock import ANY, patch

from parameterized import parameterized

from aws_lambda_builders.actions import (
    BaseAction,
    CopySourceAction,
    Purpose,
    CopyDependenciesAction,
    MoveDependenciesAction,
    CleanUpAction,
    DependencyManager,
)


class TestBaseActionInheritance(TestCase):
    def test_must_inherit(self):
        class MyAction(BaseAction):
            NAME = "myname"
            PURPOSE = Purpose.COPY_SOURCE

        action = MyAction()
        self.assertIsNotNone(action)

    def test_must_validate_name_property(self):
        with self.assertRaises(ValueError):

            class MyAction(BaseAction):
                PURPOSE = Purpose.COPY_SOURCE

    def test_must_validate_purpose_property(self):
        with self.assertRaises(ValueError):

            class MyAction(BaseAction):
                NAME = "Myaction"
                PURPOSE = "foo"


class TestBaseAction_repr(TestCase):
    def test_must_pretty_print_action_info(self):
        class MyAction(BaseAction):
            NAME = "myname"
            PURPOSE = Purpose.COPY_SOURCE
            DESCRIPTION = "description"

        action = MyAction()
        expected = "Name=myname, Purpose=COPY_SOURCE, Description=description"
        self.assertEqual(str(action), expected)


class TestCopySourceAction_execute(TestCase):
    @patch("aws_lambda_builders.actions.copytree")
    def test_must_copy(self, copytree_mock):
        source_dir = "source"
        dest_dir = "dest"
        excludes = ["*.pyc", "__pycache__"]

        action = CopySourceAction(source_dir, dest_dir, excludes=excludes)
        action.execute()

        copytree_mock.assert_called_with(source_dir, dest_dir, ignore=ANY)


class TestCopyDependenciesAction_execute(TestCase):
    @patch("aws_lambda_builders.actions.os.makedirs")
    @patch("aws_lambda_builders.actions.os.path.dirname")
    @patch("aws_lambda_builders.actions.shutil.copy2")
    @patch("aws_lambda_builders.actions.copytree")
    @patch("aws_lambda_builders.actions.os.path.isdir")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_must_copy(
        self, path_mock, listdir_mock, isdir_mock, copytree_mock, copy2_mock, dirname_mock, makedirs_mock
    ):
        source_dir = "source"
        artifact_dir = "artifact"
        dest_dir = "dest"

        listdir_mock.side_effect = [[1], [1, 2, 3]]
        path_mock.side_effect = ["dir1", "dir2", "file1", "file2"]
        isdir_mock.side_effect = [True, False]
        dirname_mock.side_effect = ["parent_dir_1"]
        action = CopyDependenciesAction(source_dir, artifact_dir, dest_dir)
        action.execute()

        listdir_mock.assert_any_call(source_dir)
        listdir_mock.assert_any_call(artifact_dir)
        copytree_mock.assert_called_once_with("dir1", "dir2")
        copy2_mock.assert_called_once_with("file1", "file2")
        makedirs_mock.assert_called_once_with("parent_dir_1", exist_ok=True)


class TestMoveDependenciesAction_execute(TestCase):
    @patch("aws_lambda_builders.actions.shutil.move")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_must_copy(self, path_mock, listdir_mock, move_mock):
        source_dir = "source"
        artifact_dir = "artifact"
        dest_dir = "dest"

        listdir_mock.side_effect = [[1], [1, 2, 3]]
        path_mock.side_effect = ["dir1", "dir2", "file1", "file2"]
        action = MoveDependenciesAction(source_dir, artifact_dir, dest_dir)
        action.execute()

        listdir_mock.assert_any_call(source_dir)
        listdir_mock.assert_any_call(artifact_dir)
        move_mock.assert_any_call("dir1", "dir2")
        move_mock.assert_any_call("file1", "file2")


class TestCleanUpAction_execute(TestCase):
    @patch("aws_lambda_builders.actions.os.remove")
    @patch("aws_lambda_builders.actions.shutil.rmtree")
    @patch("aws_lambda_builders.actions.os.path.isdir")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_must_copy(self, path_mock, listdir_mock, isdir_mock, rmtree_mock, rm_mock):
        target_dir = "target"

        listdir_mock.side_effect = [[1, 2]]
        path_mock.side_effect = ["dir", "file"]
        isdir_mock.side_effect = [True, True, False]
        action = CleanUpAction(target_dir)
        action.execute()

        listdir_mock.assert_any_call(target_dir)
        rmtree_mock.assert_any_call("dir")
        rm_mock.assert_any_call("file")


class TestDependencyManager(TestCase):
    @parameterized.expand(
        [
            (
                ["app.js", "package.js", "libs", "node_modules"],
                ["app.js", "package.js", "libs", "node_modules"],
                [("artifacts/node_modules", "dest/node_modules")],
                None,
            ),
            (
                ["file1, file2", "dep1", "dep2"],
                ["file1, file2", "dep1", "dep2"],
                [("artifacts/dep1", "dest/dep1"), ("artifacts/dep2", "dest/dep2")],
                ["dep1", "dep2"],
            ),
            (
                ["file1, file2"],
                ["file1, file2", "dep1", "dep2"],
                [("artifacts/dep1", "dest/dep1"), ("artifacts/dep2", "dest/dep2")],
                ["dep1", "dep2"],
            ),
        ]
    )
    @patch("aws_lambda_builders.actions.os.listdir")
    def test_excludes_dependencies_from_source(
        self, source_files, artifact_files, expected, mock_dependencies, patched_list_dir
    ):
        dependency_manager = DependencyManager("source", "artifacts", "dest")
        dependency_manager.IGNORE_LIST = (
            dependency_manager.IGNORE_LIST if mock_dependencies is None else mock_dependencies
        )
        patched_list_dir.side_effect = [source_files, artifact_files]
        source_destinations = list(
            TestDependencyManager._convert_strings_to_paths(list(dependency_manager.yield_source_dest()))
        )
        expected_paths = TestDependencyManager._convert_strings_to_paths(expected)
        for expected_source_dest in expected_paths:
            self.assertIn(expected_source_dest, source_destinations)

    @staticmethod
    def _convert_strings_to_paths(source_dest_list):
        return map(lambda item: (Path(item[0]), Path(item[1])), source_dest_list)
