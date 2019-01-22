from unittest import TestCase
from mock import patch

from aws_lambda_builders.actions import ActionFailedError

from aws_lambda_builders.workflows.go_dep.actions import DepEnsureAction, GoBuildAction
from aws_lambda_builders.workflows.go_dep.subproc_exec import ExecutionError


class TestDepEnsureAction(TestCase):
    @patch("aws_lambda_builders.workflows.go_dep.subproc_exec.SubprocessExec")
    def test_runs_dep_ensure(self, SubProcMock):
        """
        tests the happy path of running `dep ensure`
        """

        sub_proc_dep = SubProcMock.return_value
        action = DepEnsureAction("base", sub_proc_dep)

        action.execute()

        sub_proc_dep.run.assert_called_with(["ensure"], cwd="base")

    @patch("aws_lambda_builders.workflows.go_dep.subproc_exec.SubprocessExec")
    def test_fails_dep_ensure(self, SubProcMock):
        """
        tests failure, something being returned on stderr
        """

        sub_proc_dep = SubProcMock.return_value
        sub_proc_dep.run.side_effect = ExecutionError(message="boom!")
        action = DepEnsureAction("base", sub_proc_dep)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "Exec Failed: boom!")


class TestGoBuildAction(TestCase):
    @patch("aws_lambda_builders.workflows.go_dep.subproc_exec.SubprocessExec")
    def test_runs_go_build(self, SubProcMock):
        """
        tests the happy path of running `dep ensure`
        """

        sub_proc_go = SubProcMock.return_value
        action = GoBuildAction("base", "source", "output", sub_proc_go, env={})

        action.execute()

        sub_proc_go.run.assert_called_with(["build", "-o", "output", "source"],
                                           cwd="source",
                                           env={"GOOS": "linux", "GOARCH": "amd64"})

    @patch("aws_lambda_builders.workflows.go_dep.subproc_exec.SubprocessExec")
    def test_fails_go_build(self, SubProcMock):
        """
        tests failure, something being returned on stderr
        """

        sub_proc_go = SubProcMock.return_value
        sub_proc_go.run.side_effect = ExecutionError(message="boom!")
        action = GoBuildAction("base", "source", "output", sub_proc_go, env={})

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "Exec Failed: boom!")
