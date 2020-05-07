import os

from unittest import TestCase

from mock import patch, ANY

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.custom_make.utils import OSUtils
from aws_lambda_builders.workflows.custom_make.actions import CustomMakeAction
from aws_lambda_builders.workflows.custom_make.make import MakeExecutionError


class TestProvidedMakeAction(TestCase):
    def setUp(self):
        self.original_env = OSUtils().environ()
        os.environ = {}

    def tearDown(self):
        os.environ = self.original_env

    @patch("aws_lambda_builders.workflows.custom_make.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.custom_make.make.SubProcessMake")
    def test_call_makefile_target(self, OSUtilMock, SubprocessMakeMock):
        osutils = OSUtilMock.return_value
        subprocess_make = SubprocessMakeMock.return_value

        action = CustomMakeAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            osutils=osutils,
            subprocess_make=subprocess_make,
            build_logical_id="logical_id",
        )

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action.execute()

        subprocess_make.run.assert_called_with(
            ["--makefile", "manifest", "build-logical_id"], cwd="scratch_dir", env=ANY
        )

    @patch("aws_lambda_builders.workflows.custom_make.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.custom_make.make.SubProcessMake")
    def test_makefile_target_fails(self, OSUtilMock, SubprocessMakeMock):
        osutils = OSUtilMock.return_value
        subprocess_make = SubprocessMakeMock.return_value

        action = CustomMakeAction(
            "artifacts",
            "scratch_dir",
            "manifest",
            osutils=osutils,
            subprocess_make=subprocess_make,
            build_logical_id="logical_id",
        )

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        subprocess_make.run.side_effect = [MakeExecutionError(message="failure")]

        with self.assertRaises(ActionFailedError):
            action.execute()
        subprocess_make.run.assert_called_with(
            ["--makefile", "manifest", "build-logical_id"], cwd="scratch_dir", env=ANY
        )
