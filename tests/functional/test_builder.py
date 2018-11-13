
import sys
import os
import shutil
import tempfile

from unittest import TestCase
from aws_lambda_builders.builder import LambdaBuilder


class TestBuilderWithHelloWorkflow(TestCase):

    HELLO_WORKFLOW_MODULE = "hello_workflow.write_hello"
    TEST_WORKFLOWS_FOLDER = os.path.join(os.path.dirname(__file__), "testdata", "workflows")

    def setUp(self):
        # Temporarily add the testdata folder to PYTHOHNPATH
        sys.path.append(self.TEST_WORKFLOWS_FOLDER)

        self.source_dir = tempfile.mkdtemp()
        self.artifacts_dir = tempfile.mkdtemp()
        self.hello_builder = LambdaBuilder(language="test",
                                           dependency_manager="test",
                                           application_framework="test",
                                           supported_workflows=[
                                               self.HELLO_WORKFLOW_MODULE
                                           ])

        # The builder should write a file called hello.txt with contents "Hello World"
        self.expected_filename = os.path.join(self.artifacts_dir, 'hello.txt')
        self.expected_contents = "Hello World"

    def tearDown(self):
        self.hello_builder._clear_workflows()
        shutil.rmtree(self.source_dir)
        shutil.rmtree(self.artifacts_dir)

        # Remove the workflows folder from PYTHONPATH
        sys.path.remove(self.TEST_WORKFLOWS_FOLDER)

    def test_run_hello_workflow(self):

        self.hello_builder.build(self.source_dir,
                                 self.artifacts_dir,
                                 "/ignored",
                                 "/ignored")

        self.assertTrue(os.path.exists(self.expected_filename))
        contents = ''
        with open(self.expected_filename, 'r') as fp:
            contents = fp.read()

        self.assertEquals(contents, self.expected_contents)
