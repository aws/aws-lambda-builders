import os
import shutil
import tempfile

from unittest import TestCase

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError

class TestRubyWorkflow(TestCase):
    """
    Verifies that `ruby` workflow works by building a Lambda using Bundler
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        self.builder = LambdaBuilder(language="ruby",
                                     dependency_manager="bundler",
                                     application_framework=None)
        self.runtime="ruby2.5"

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)

    def test_builds_project_without_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                           os.path.join(source_dir, "Gemfile"),
                           runtime=self.runtime)
        expected_files = {"handler.rb", "Gemfile", "Gemfile.lock", ".bundle", "vendor"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEquals(expected_files, output_files)

    def test_builds_project_with_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "with-deps")
        self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                           os.path.join(source_dir, "Gemfile"),
                           runtime=self.runtime)
        expected_files = {"handler.rb", "Gemfile", "Gemfile.lock", ".bundle", "vendor"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEquals(expected_files, output_files)

    def test_fails_if_bundler_cannot_resolve_dependencies(self):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-deps")
        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(source_dir, self.artifacts_dir, self.scratch_dir,
                               os.path.join(source_dir, "Gemfile"),
                               runtime=self.runtime)
        self.assertIn("RubyBundlerBuilder:RubyBundle - Bundler Failed: ",
                      str(ctx.exception))
