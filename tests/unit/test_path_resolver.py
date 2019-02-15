from unittest import TestCase

import os
import mock

from aws_lambda_builders import utils
from aws_lambda_builders.path_resolver import PathResolver


class TestPathResolver(TestCase):

    def setUp(self):
        self.path_resolver = PathResolver(runtime="chitti2.0", binary="chitti")

    def test_inits(self):
        self.assertEquals(self.path_resolver.runtime, "chitti2.0")
        self.assertEquals(self.path_resolver.binary, "chitti")

    def test_which_fails(self):
        with self.assertRaises(ValueError):
            utils.which = lambda x: None
            self.path_resolver._which()

    def test_which_success_immediate(self):
        with mock.patch.object(self.path_resolver, '_which') as which_mock:
            which_mock.return_value = os.getcwd()
            self.assertEquals(self.path_resolver.exec_paths, os.getcwd())
