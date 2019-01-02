import os
from unittest import TestCase

import mock
import whichcraft

from aws_lambda_builders.workflows.python_pip.path_resolver import PythonPathResolver


class TestPythonPathResolver(TestCase):

    def setUp(self):
        self.path_resolver = PythonPathResolver(runtime="python3.7")

    def test_inits(self):
        self.assertEquals(self.path_resolver.language, "python")
        self.assertEquals(self.path_resolver.runtime, "python3.7")
        self.assertEquals(self.path_resolver.executables,
                          [self.path_resolver.runtime, self.path_resolver.language])

    def test_which_fails(self):
        with self.assertRaises(ValueError):
            whichcraft.which = lambda x: None
            self.path_resolver._which()

    def test_which_success_immediate(self):
        with mock.patch.object(self.path_resolver, '_which') as which_mock:
            which_mock.return_value = os.getcwd()
            self.assertEquals(self.path_resolver.exec_path, os.getcwd())
