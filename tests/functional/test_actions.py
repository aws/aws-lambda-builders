import os
from pathlib import Path
import tempfile
from unittest import TestCase
from parameterized import parameterized


from aws_lambda_builders.actions import CopyDependenciesAction, LinkSinglePathAction, MoveDependenciesAction
from aws_lambda_builders.utils import copytree
from tests.testing_utils import read_link_without_junction_prefix


class TestCopyDependenciesAction(TestCase):
    @parameterized.expand(
        [
            ("single_file",),
            ("multiple_files",),
            ("empty_subfolders",),
        ]
    )
    def test_copy_dependencies_action(self, source_folder):
        curr_dir = Path(__file__).resolve().parent
        test_folder = os.path.join(curr_dir, "testdata", source_folder)
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_source = os.path.join(tmpdir, "empty_source")
            target = os.path.join(tmpdir, "target")

            os.mkdir(empty_source)

            copy_dependencies_action = CopyDependenciesAction(empty_source, test_folder, target)
            copy_dependencies_action.execute()

            self.assertEqual(os.listdir(test_folder), os.listdir(target))

    def test_must_maintain_symlinks_if_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            artifact_dir = os.path.join(tmpdir, "artifact")
            destination_dir = os.path.join(tmpdir, "destination")

            source_node_modules = os.path.join(source_dir, "node_modules")
            os.makedirs(source_node_modules)
            os.makedirs(artifact_dir)
            os.symlink(source_node_modules, os.path.join(artifact_dir, "node_modules"))

            copy_dependencies_action = CopyDependenciesAction(
                source_dir=source_dir,
                artifact_dir=artifact_dir,
                destination_dir=destination_dir,
                maintain_symlinks=True,
            )
            copy_dependencies_action.execute()

            destination_node_modules = os.path.join(destination_dir, "node_modules")
            self.assertTrue(os.path.islink(destination_node_modules))
            destination_node_modules_target = read_link_without_junction_prefix(destination_node_modules)
            self.assertEqual(destination_node_modules_target, source_node_modules)

    def test_must_not_maintain_symlinks_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            artifact_dir = os.path.join(tmpdir, "artifact")
            destination_dir = os.path.join(tmpdir, "destination")

            source_node_modules = os.path.join(source_dir, "node_modules")
            os.makedirs(os.path.join(source_node_modules, "some_package"))
            os.makedirs(artifact_dir)
            os.symlink(source_node_modules, os.path.join(artifact_dir, "node_modules"))

            copy_dependencies_action = CopyDependenciesAction(
                source_dir=source_dir, artifact_dir=artifact_dir, destination_dir=destination_dir
            )
            copy_dependencies_action.execute()

            destination_node_modules = os.path.join(destination_dir, "node_modules")
            self.assertFalse(os.path.islink(destination_node_modules))
            self.assertEqual(os.listdir(destination_node_modules), os.listdir(source_node_modules))


class TestLinkSinglePathAction(TestCase):
    def test_link_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)
            dest_dir = os.path.join(tmpdir, "dest")

            link_action = LinkSinglePathAction(source_dir, dest_dir)
            link_action.execute()

            self.assertTrue(os.path.islink(dest_dir))
            dest_dir_target = read_link_without_junction_prefix(dest_dir)
            self.assertEqual(dest_dir_target, source_dir)


class TestMoveDependenciesAction(TestCase):
    @parameterized.expand(
        [
            ("single_file",),
            ("multiple_files",),
            ("empty_subfolders",),
        ]
    )
    def test_move_dependencies_action(self, source_folder):
        curr_dir = Path(__file__).resolve().parent
        test_folder = os.path.join(curr_dir, "testdata", source_folder)
        with tempfile.TemporaryDirectory() as tmpdir:
            test_source = os.path.join(tmpdir, "test_source")
            empty_source = os.path.join(tmpdir, "empty_source")
            target = os.path.join(tmpdir, "target")

            os.mkdir(test_source)
            os.mkdir(empty_source)

            copytree(test_folder, test_source)

            move_dependencies_action = MoveDependenciesAction(empty_source, test_source, target)
            move_dependencies_action.execute()

            self.assertEqual(os.listdir(test_folder), os.listdir(target))
