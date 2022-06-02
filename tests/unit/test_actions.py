from unittest import TestCase
from mock import patch, ANY, Mock

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
    @patch("aws_lambda_builders.actions.DependencyManager._set_dependencies")
    def test_yields_source_and_destination_directories(self, set_deps):
        dependency_manager = DependencyManager("source", "artifacts", "dest")
        dependency_manager._dependencies = ["dep1", "dep2", "dep3"]
        idx = 0
        for source, dest in dependency_manager.yield_source_dest():
            self.assertEqual(source, f"artifacts/{dependency_manager._dependencies[idx]}")
            self.assertEqual(dest, f"dest/{dependency_manager._dependencies[idx]}")
            idx += 1

    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.DependencyManager._get_source_files_exclude_deps")
    def test_set_dependencies(self, get_files, artifact_list_dir):
        artifact_list_dir.return_value = ["file1, file2", "dep1", "dep2"]
        get_files.return_value = {"file1, file2"}
        dependency_manager = DependencyManager("source", "artifacts", "dest")
        self.assertEqual(dependency_manager._dependencies, {"dep1", "dep2"})

    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.DependencyManager._set_dependencies")
    def test_get_source_files_exclude_deps(self, set_deps, source_list_dir):
        source_list_dir.return_value = ["app.js", "package.js", "libs", "node_modules"]
        dependency_manager = DependencyManager("source", "artifacts", "dest")
        source_files = dependency_manager._get_source_files_exclude_deps()
        self.assertEqual(source_files, {"app.js", "package.js", "libs"})
