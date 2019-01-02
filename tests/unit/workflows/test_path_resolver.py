from unittest import TestCase

from aws_lambda_builders.path_resolver import PathResolver


class TestPathResolver(TestCase):

    def setUp(self):
        self.path_resolver = PathResolver(runtime="chitti2.0")

    def test_inits(self):
        self.assertEquals(self.path_resolver.runtime, "chitti2.0")

    def test_exec_path(self):
        self.assertEquals(self.path_resolver.runtime, self.path_resolver.exec_path)