import os
from pathlib import Path
import tempfile
from unittest import TestCase
from parameterized import parameterized


from aws_lambda_builders.actions import CopyDependenciesAction, MoveDependenciesAction
from aws_lambda_builders.utils import copytree


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

            self.assertEqual(sorted(os.listdir(test_folder)), sorted(os.listdir(target)))


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

            self.assertEqual(sorted(os.listdir(test_folder)), sorted(os.listdir(target)))
