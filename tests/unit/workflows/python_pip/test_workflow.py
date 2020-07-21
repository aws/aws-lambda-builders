import pytest
import pathlib
from unittest import TestCase, mock

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflows.python_pip.validator import PythonRuntimeValidator
from aws_lambda_builders.workflows.python_pip.workflow import PythonPipBuildAction, PythonPipWorkflow


class TestPythonPipWorkflow(TestCase):
    def setUp(self):
        self.workflow = PythonPipWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="python3.7")

    def test_workflow_sets_up_actions(self):
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonPipBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_validator(self):
        for validator in self.workflow.get_validators():
            self.assertTrue(isinstance(validator, PythonRuntimeValidator))


@pytest.mark.parametrize("use_samignore", (False, False))
def test_use_sam_ignore(tmpdir, use_samignore: bool):
    """
    Verify if there is a `.samignore` workflow will give that preference
    over the default files to exclude.
    """

    sam_ignore = pathlib.Path(f"{tmpdir}/.samignore")

    if use_samignore:
        sam_ignore.write_text("foo*.txt\n*-bar.so\n")

    pathlib.Path = mock.MagicMock(return_value=sam_ignore)
    mock.patch.object(sam_ignore, "exists", return_value=use_samignore)

    _workflow = PythonPipWorkflow("source", "artifacts", "scratch_dir", "manifest", runtime="python3.7")

    pathlib.Path.assert_called_once_with("./.samignore")

    if use_samignore:
        assert _workflow.excluded_files == ["foo*.txt", "*-bar.so"]
    else:
        assert _workflow.excluded_files == _workflow._DEFAULT_EXCLUDED_FILES
