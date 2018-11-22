import os
from unittest import TestCase

import mock

from aws_lambda_builders.path_resolver import PathResolver


class TestPathResolver(TestCase):

    def setUp(self):
        self.path_resolver = PathResolver(language="chitti",runtime="chitti2.0")

    def test_inits(self):
        self.assertEquals(self.path_resolver.language, "chitti")
        self.assertEquals(self.path_resolver.runtime, "chitti2.0")
        self.assertEquals(self.path_resolver.executables,
                          [self.path_resolver.runtime, self.path_resolver.language])

    def test_which_fails(self):
        with self.assertRaises(ValueError):
            self.path_resolver.path

    def test_which_success_immediate(self):
        with mock.patch.object(self.path_resolver,'_which') as which_mock:
            which_mock.return_value = os.getcwd()
            self.assertEquals(self.path_resolver.path, os.getcwd())


