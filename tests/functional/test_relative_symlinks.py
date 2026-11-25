import os
import subprocess
from contextlib import nullcontext
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from parameterized import parameterized

from aws_lambda_builders.actions import CopyDependenciesAction
from aws_lambda_builders.utils import copytree


class TestRelativeSourceSymlinks(TestCase):
    @parameterized.expand(
        product(("copytree", "dependencies"), ("file", "directory"), (False, True), ("direct", "symlink", "junction"))
    )
    def test_relative_target(self, entrypoint, kind, force_copy, parent_kind):
        if parent_kind == "junction" and os.name != "nt":
            self.skipTest("NTFS junctions require Windows")
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            physical_source = root / "real" / "artifacts"
            physical_source.mkdir(parents=True)
            target = root / "real" / "target"
            decoy = root / "target"
            if kind == "directory":
                target.mkdir()
                decoy.mkdir()
                (target / "data.txt").write_text("physical target")
                (decoy / "data.txt").write_text("logical target")
            else:
                target.write_text("physical target")
                decoy.write_text("logical target")
            (physical_source / "dependency").symlink_to(
                os.path.join("..", "target"), target_is_directory=kind == "directory"
            )

            source = physical_source
            if parent_kind != "direct":
                source = root / "alias"
                if parent_kind == "symlink":
                    source.symlink_to(physical_source, target_is_directory=True)
                else:
                    subprocess.run(
                        ["cmd.exe", "/d", "/c", "mklink", "/J", str(source), str(physical_source)],
                        check=True,
                        capture_output=True,
                    )
            expected = decoy if parent_kind == "junction" else target
            self.assertTrue((source / "dependency").samefile(expected))
            empty_source = root / "source"
            empty_source.mkdir()
            destination = root / "destination"
            working = root / "working"
            working.mkdir()

            old_cwd = os.getcwd()
            try:
                os.chdir(working)
                symlink_failure = (
                    patch("aws_lambda_builders.utils.os.symlink", side_effect=OSError("privilege not held"))
                    if force_copy
                    else nullcontext()
                )
                with symlink_failure:
                    if entrypoint == "copytree":
                        copytree(str(source), str(destination), maintain_symlinks=True)
                    else:
                        CopyDependenciesAction(
                            str(empty_source), str(source), str(destination), maintain_symlinks=True
                        ).execute()
            finally:
                os.chdir(old_cwd)

            result = destination / "dependency"
            self.assertEqual(result.is_symlink(), not force_copy)
            data = result / "data.txt" if kind == "directory" else result
            self.assertEqual(data.read_text(), "logical target" if parent_kind == "junction" else "physical target")
            if not force_copy:
                self.assertTrue(result.samefile(expected))

    @skipUnless(os.name == "nt", "Windows volume-root traversal")
    def test_rejects_target_that_escapes_volume_root(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            destination = root / "destination"
            target = root / "target"
            target.write_text("must not be selected by normalizing an invalid link")
            raw_target = os.path.join(*([os.pardir] * 64), os.path.splitdrive(str(target))[1].lstrip("\\/"))
            link = source / "dependency"
            link.symlink_to(raw_target)
            with self.assertRaises(OSError):
                link.read_bytes()

            with self.assertRaisesRegex(OSError, "volume root"):
                copytree(str(source), str(destination), maintain_symlinks=True)
            self.assertFalse(os.path.lexists(destination / "dependency"))
