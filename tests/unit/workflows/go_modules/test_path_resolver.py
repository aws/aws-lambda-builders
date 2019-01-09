import os
from unittest import TestCase

import mock

from aws_lambda_builders.workflows.go_modules.path_resolver import GoPathResolver


class TestPythonPathResolver(TestCase):

    def setUp(self):
        self.path_resolver = GoPathResolver(runtime="go1.x")

    def test_inits(self):
        self.assertEquals(self.path_resolver.language, "go")
        self.assertEquals(self.path_resolver.runtime, "go1.x")
        self.assertEquals(self.path_resolver.executables,
                          [self.path_resolver.language])

    def test_which_fails(self):
        path_resolver = GoPathResolver(runtime="go1.x", which=lambda x: None)
        with self.assertRaises(ValueError):
            path_resolver._which()

    def test_which_success_immediate(self):
        with mock.patch.object(self.path_resolver, '_which') as which_mock:
            which_mock.return_value = os.getcwd()
            self.assertEquals(self.path_resolver.exec_path, os.getcwd())
