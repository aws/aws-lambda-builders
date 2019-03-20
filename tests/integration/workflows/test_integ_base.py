import shutil
import os
import tempfile
from unittest import TestCase

from aws_lambda_builders.utils import copytree


class TestIntegBase(TestCase):

    def setUp(self):
        self.ro_source_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.chmod(self.ro_source_dir, 0o755)
        shutil.rmtree(self.ro_source_dir)

    def ro_source(self, source_dir):
        copytree(source_dir, self.ro_source_dir)
        os.chmod(self.ro_source_dir, 0o555)
