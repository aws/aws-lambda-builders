import os
import shutil
import tempfile
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
    LinkSinglePathAction,
    LinkSourceAction,
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

        copytree_mock.assert_called_with(source_dir, dest_dir, ignore=ANY, maintain_symlinks=False)


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
        copytree_mock.assert_called_once_with("dir1", "dir2", maintain_symlinks=False)
        copy2_mock.assert_called_once_with("file1", "file2")
        makedirs_mock.assert_called_once_with("parent_dir_1", exist_ok=True)

    @patch("aws_lambda_builders.actions.os.makedirs")
    @patch("aws_lambda_builders.actions.os.path.dirname")
    @patch("aws_lambda_builders.actions.shutil.copy2")
    @patch("aws_lambda_builders.actions.copytree")
    @patch("aws_lambda_builders.actions.os.path.isdir")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_must_copy_with_external_manifest(
        self, path_mock, listdir_mock, isdir_mock, copytree_mock, copy2_mock, dirname_mock, makedirs_mock
    ):
        source_dir = "source"
        artifact_dir = "artifact"
        dest_dir = "dest"
        manifest_dir = "manifest"

        listdir_mock.side_effect = [[1], [2], [1, 2, 3, 4]]
        path_mock.side_effect = ["dir1", "dir2", "file1", "file2"]
        isdir_mock.side_effect = [True, False]
        dirname_mock.side_effect = ["parent_dir_1"]
        action = CopyDependenciesAction(source_dir, artifact_dir, dest_dir, manifest_dir=manifest_dir)
        action.execute()

        listdir_mock.assert_any_call(source_dir)
        listdir_mock.assert_any_call(manifest_dir)
        listdir_mock.assert_any_call(artifact_dir)
        copytree_mock.assert_called_once_with("dir1", "dir2", maintain_symlinks=False)
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

    @patch("aws_lambda_builders.actions.shutil.move")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_must_copy_with_manifest(self, path_mock, listdir_mock, move_mock):
        source_dir = "source"
        artifact_dir = "artifact"
        dest_dir = "dest"
        manifest_dir = "manifest"

        listdir_mock.side_effect = [[1], [2], [1, 2, 3]]
        path_mock.side_effect = ["dir1", "dir2", "file1", "file2"]
        action = MoveDependenciesAction(source_dir, artifact_dir, dest_dir, manifest_dir=manifest_dir)
        action.execute()

        listdir_mock.assert_any_call(source_dir)
        listdir_mock.assert_any_call(manifest_dir)
        listdir_mock.assert_any_call(artifact_dir)
        move_mock.assert_any_call("dir1", "dir2")


class TestCleanUpAction_execute(TestCase):
    @patch("aws_lambda_builders.actions.os.remove")
    @patch("aws_lambda_builders.actions.shutil.rmtree")
    @patch("aws_lambda_builders.actions.os.path.isdir")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_removes_directories_and_files(self, path_mock, listdir_mock, isdir_mock, rmtree_mock, rm_mock):
        target_dir = "target"

        listdir_mock.side_effect = [[1, 2]]
        path_mock.side_effect = ["dir", "file"]
        isdir_mock.side_effect = [True, True, False]
        action = CleanUpAction(target_dir)
        action.execute()

        listdir_mock.assert_any_call(target_dir)
        rmtree_mock.assert_any_call("dir")
        rm_mock.assert_any_call("file")

    @patch("aws_lambda_builders.actions.os.unlink")
    @patch("aws_lambda_builders.actions.os.path.islink")
    @patch("aws_lambda_builders.actions.os.path.isdir")
    @patch("aws_lambda_builders.actions.os.listdir")
    @patch("aws_lambda_builders.actions.os.path.join")
    def test_can_handle_symlinks(self, join_mock, listdir_mock, isdir_mock, islink_mock, unlink_mock):
        target_dir = "target"

        isdir_mock.side_effect = [True]
        listdir_mock.side_effect = [["link"]]
        join_mock.side_effect = ["target/link"]
        islink_mock.side_effect = [True]
        action = CleanUpAction(target_dir)
        action.execute()

        unlink_mock.assert_called_once_with("target/link")


class TestDependencyManager(TestCase):
    @parameterized.expand(
        [
            (
                ["app.js", "package.js", "libs", "node_modules"],
                ["app.js", "package.js", "libs", "node_modules"],
                None,
                [("artifacts/node_modules", "dest/node_modules")],
                None,
                None,
            ),
            (
                ["app.js", "libs", "node_modules"],
                ["app.js", "package.js", "libs", "node_modules"],
                ["package.js"],
                [("artifacts/node_modules", "dest/node_modules")],
                None,
                "manifest",
            ),
            (
                ["file1, file2", "dep1", "dep2"],
                ["file1, file2", "dep1", "dep2"],
                None,
                [("artifacts/dep1", "dest/dep1"), ("artifacts/dep2", "dest/dep2")],
                ["dep1", "dep2"],
                None,
            ),
            (
                ["file1, file2"],
                ["file1, file2", "dep1", "dep2"],
                None,
                [("artifacts/dep1", "dest/dep1"), ("artifacts/dep2", "dest/dep2")],
                ["dep1", "dep2"],
                None,
            ),
        ]
    )
    @patch("aws_lambda_builders.actions.os.listdir")
    def test_excludes_dependencies_from_source(
        self,
        source_files,
        artifact_files,
        manifest_files,
        expected,
        mock_dependencies,
        manifest_dir,
        patched_list_dir,
    ):
        dependency_manager = DependencyManager("source", "artifacts", "dest", manifest_dir)
        dependency_manager.IGNORE_LIST = (
            dependency_manager.IGNORE_LIST if mock_dependencies is None else mock_dependencies
        )
        patched_list_dir.side_effect = (
            [source_files, manifest_files, artifact_files] if manifest_dir else [source_files, artifact_files]
        )
        source_destinations = list(
            TestDependencyManager._convert_strings_to_paths(list(dependency_manager.yield_source_dest()))
        )
        expected_paths = TestDependencyManager._convert_strings_to_paths(expected)
        for expected_source_dest in expected_paths:
            self.assertIn(expected_source_dest, source_destinations)

    @staticmethod
    def _convert_strings_to_paths(source_dest_list):
        return map(lambda item: (Path(item[0]), Path(item[1])), source_dest_list)


class TestLinkSourceAction(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.source_dir = Path(self._tmp.name, "deps")
        self.dest_dir = Path(self._tmp.name, "artifacts")
        (self.source_dir / "somepkg").mkdir(parents=True)
        (self.source_dir / "somepkg" / "__init__.py").write_text("hello")
        (self.source_dir / "six.py").write_text("six")
        self.dest_dir.mkdir()

    def _execute(self):
        LinkSourceAction(str(self.source_dir), str(self.dest_dir)).execute()

    def _assert_linked(self):
        for name in ("somepkg", "six.py"):
            destination = self.dest_dir / name
            self.assertTrue(destination.is_symlink(), f"{name} should be a symlink")
            self.assertEqual(os.path.realpath(destination), str((self.source_dir / name).resolve()))
        self.assertEqual((self.dest_dir / "somepkg" / "__init__.py").read_text(), "hello")

    def test_links_into_an_empty_destination(self):
        self._execute()
        self._assert_linked()

    def test_replaces_a_real_directory_left_by_an_earlier_copying_build(self):
        # A build that copied dependencies leaves real directories behind. Without --clean they
        # survive into the next build, and os.remove() cannot remove a directory.
        stale = self.dest_dir / "somepkg"
        stale.mkdir()
        (stale / "__init__.py").write_text("stale")
        (self.dest_dir / "six.py").write_text("stale")

        self._execute()
        self._assert_linked()

    def test_replaces_a_dangling_symlink(self):
        # A dangling symlink is not exists(), so it used to be left in place and os.symlink then
        # raised FileExistsError, which create_symlink_or_copy swallowed into a full copy.
        (self.dest_dir / "six.py").symlink_to(self._tmp.name + "/gone")
        self.assertFalse((self.dest_dir / "six.py").exists())

        self._execute()
        self._assert_linked()

    def test_is_idempotent(self):
        self._execute()
        self._execute()
        self._assert_linked()

    def test_skips_a_source_that_does_not_exist(self):
        # CopySourceAction warns and continues here; the layer path must not turn that into a failure.
        missing = Path(self._tmp.name, "never-created")

        LinkSourceAction(str(missing), str(self.dest_dir)).execute()

        self.assertEqual(os.listdir(self.dest_dir), [])

    def test_prunes_a_link_to_a_dependency_dropped_from_the_manifest(self):
        # The link loop only visits names still in the source, so a dependency dropped from the
        # manifest keeps its link from the previous build. It dangles once the dependencies dir is
        # cleaned, and both zipfile.write and tarfile.add(dereference=True) raise FileNotFoundError
        # on a broken link rather than skipping it.
        self._execute()
        shutil.rmtree(self.source_dir / "somepkg")
        self.assertTrue((self.dest_dir / "somepkg").is_symlink())

        self._execute()

        self.assertNotIn("somepkg", os.listdir(self.dest_dir))
        self.assertTrue((self.dest_dir / "six.py").is_symlink())
        for root, _, files in os.walk(self.dest_dir, followlinks=True):
            for name in files:
                self.assertTrue(Path(root, name).exists(), f"{name} is a broken link")

    def test_prunes_a_link_whose_recorded_target_is_relative(self):
        # os.readlink returns a relative target verbatim, so it means nothing without the link's
        # own parent. Without that join the containment check rejects the link and it survives.
        self._execute()
        (self.dest_dir / "somepkg").unlink()
        os.symlink(os.path.join("..", "deps", "somepkg"), self.dest_dir / "somepkg")
        shutil.rmtree(self.source_dir / "somepkg")
        self.assertTrue((self.dest_dir / "somepkg").is_symlink())

        self._execute()

        self.assertNotIn("somepkg", os.listdir(self.dest_dir))

    def test_keeps_a_broken_link_whose_target_tree_is_gone_entirely(self):
        # samefile() raises FileNotFoundError when either side is missing, so a link into a tree
        # that has been removed wholesale must be rejected before the comparison, not during it.
        orphan = self.dest_dir / "orphan"
        orphan.symlink_to(Path(self._tmp.name, "removed-tree", "pkg"))

        self._execute()

        self.assertTrue(orphan.is_symlink())
        self._assert_linked()

    def test_keeps_a_broken_link_pointing_outside_the_source_directory(self):
        # nodejs_npm_esbuild links into a scratch_dir that already holds copied source. An entry
        # this action did not create is not ours to reconcile, even when it is broken.
        foreign = self.dest_dir / "foreign"
        foreign.symlink_to(Path(self._tmp.name, "elsewhere"))

        self._execute()

        self.assertTrue(foreign.is_symlink())
        self._assert_linked()

    def test_leaves_a_real_stale_entry_from_a_dropped_dependency(self):
        # Only broken links are ours to reconcile. A real directory left by an earlier copying
        # build is stale but still packages and runs, which is how it behaved before this change;
        # pruning build artifacts a build did not produce belongs to the caller, not this action.
        stale = self.dest_dir / "dropped"
        stale.mkdir()
        (stale / "__init__.py").write_text("stale")

        self._execute()

        self.assertTrue(stale.is_dir())
        self.assertEqual((stale / "__init__.py").read_text(), "stale")

    def test_keeps_a_working_link_into_the_source_tree_under_another_name(self):
        # Only BROKEN links are reconciled. A link that still resolves is serving someone, even
        # when it points into our source tree under a name the source directory does not list.
        alias = self.dest_dir / "alias.py"
        alias.symlink_to(self.source_dir / "somepkg" / "__init__.py")
        self.assertTrue(alias.exists())

        self._execute()

        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.read_text(), "hello")

    def test_tolerates_an_empty_source_and_a_destination_that_was_never_created(self):
        # With at least one source file the link loop creates the destination on the way past, so
        # this is the only ordering that reaches the prune step with no destination directory: an
        # empty dependencies dir (pip downloaded nothing) and a first build.
        empty_source = Path(self._tmp.name, "empty-deps")
        empty_source.mkdir()
        dest = Path(self._tmp.name, "artifacts-2")

        LinkSourceAction(str(empty_source), str(dest)).execute()

        self.assertFalse(dest.exists())


class TestLinkSinglePathAction(TestCase):
    @patch("aws_lambda_builders.actions.os.makedirs")
    @patch("aws_lambda_builders.utils.create_symlink_or_copy")
    def test_skips_non_existent_source(self, mock_create_symlink_or_copy, mock_makedirs):
        src = "src/path"
        dest = "dest/path"

        LinkSinglePathAction(source=src, dest=dest).execute()
        mock_create_symlink_or_copy.assert_not_called()
        mock_makedirs.assert_not_called()
