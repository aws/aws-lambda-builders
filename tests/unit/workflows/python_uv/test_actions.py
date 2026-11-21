import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from aws_lambda_builders.workflows.python_uv.actions import PythonUvCompileSourceAction
from aws_lambda_builders.workflows.python_uv.exceptions import MissingUvError


class TestPythonUvCompileSourceAction(TestCase):
    def setUp(self):
        self.source_dir = tempfile.mkdtemp()
        self.artifacts_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir)
        self.addCleanup(shutil.rmtree, self.artifacts_dir)

    def _execute(self, runtime="python3.13", excludes=("venv", "*.egg-info")):
        with (
            patch("aws_lambda_builders.workflows.python_uv.actions.SubprocessUv"),
            patch("aws_lambda_builders.workflows.python_uv.actions.UvRunner") as runner_class,
        ):
            PythonUvCompileSourceAction(self.source_dir, self.artifacts_dir, runtime, excludes).execute()
        return runner_class.return_value.compile_bytecode

    def test_compiles_only_what_was_copied_from_the_source(self):
        for root in (self.source_dir, self.artifacts_dir):
            Path(root, "app.py").touch()
            Path(root, "pkg").mkdir()
            Path(root, "requirements.txt").touch()
        # Excluded from the copy, so not part of the function's source, even where the
        # artifacts directory has an entry of the same name
        for root in (self.source_dir, self.artifacts_dir):
            Path(root, "venv").mkdir()
            Path(root, "app.egg-info").mkdir()
        # Installed dependencies, already compiled by the dependency build
        Path(self.artifacts_dir, "six.py").touch()
        Path(self.artifacts_dir, "requests").mkdir()

        compile_bytecode = self._execute()

        compile_bytecode.assert_called_once_with(
            "3.13", [os.path.join(self.artifacts_dir, "app.py"), os.path.join(self.artifacts_dir, "pkg")]
        )

    def test_does_nothing_without_python_source(self):
        Path(self.source_dir, "requirements.txt").touch()
        Path(self.artifacts_dir, "requirements.txt").touch()

        self._execute().assert_not_called()

    def test_passes_no_python_version_without_a_runtime(self):
        Path(self.source_dir, "app.py").touch()
        Path(self.artifacts_dir, "app.py").touch()

        self._execute(runtime=None).assert_called_once_with(None, [os.path.join(self.artifacts_dir, "app.py")])

    def test_does_nothing_without_a_source_directory(self):
        shutil.rmtree(self.source_dir)
        self.addCleanup(os.mkdir, self.source_dir)

        self._execute().assert_not_called()

    def test_warns_instead_of_failing_when_uv_is_missing(self):
        Path(self.source_dir, "app.py").touch()
        Path(self.artifacts_dir, "app.py").touch()

        with (
            patch("aws_lambda_builders.workflows.python_uv.actions.SubprocessUv", side_effect=MissingUvError()),
            self.assertLogs("aws_lambda_builders.workflows.python_uv.actions", level="WARNING") as logs,
        ):
            PythonUvCompileSourceAction(self.source_dir, self.artifacts_dir, "python3.13").execute()

        self.assertIn("Skipping bytecode compilation of the source: uv executable not found", logs.output[0])
