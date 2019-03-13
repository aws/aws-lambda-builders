import os
import tempfile
from unittest import TestCase

from aws_lambda_builders.utils import permissions


class TestUtils(TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.entry_mode = 0o555
        self.exit_mode = 0o755

    def test_permissions(self):
        with permissions(directory=self.directory, entry_mode=self.entry_mode, exit_mode=self.exit_mode):
            self.assertIn(oct(self.entry_mode)[2:], oct(os.lstat(self.directory).st_mode))
        self.assertIn(oct(self.exit_mode)[2:], oct(os.lstat(self.directory).st_mode))
