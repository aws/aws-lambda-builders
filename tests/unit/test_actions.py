
from unittest import TestCase
from mock import patch, ANY

from aws_lambda_builders.actions import BaseAction, CopySourceAction, Purpose


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
