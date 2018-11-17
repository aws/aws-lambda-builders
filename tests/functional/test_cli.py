
import json
import os
import shutil
import tempfile
import subprocess
import copy

from unittest import TestCase
from parameterized import parameterized


class TestCliWithHelloWorkflow(TestCase):

    HELLO_WORKFLOW_MODULE = "hello_workflow.write_hello"
    TEST_WORKFLOWS_FOLDER = os.path.join(os.path.dirname(__file__), "testdata", "workflows")

    def setUp(self):

        self.source_dir = tempfile.mkdtemp()
        self.artifacts_dir = tempfile.mkdtemp()

        # Capabilities supported by the Hello workflow
        self.language = "test"
        self.dependency_manager = "test"
        self.application_framework = "test"

        # The builder should write a file called hello.txt with contents "Hello World"
        self.expected_filename = os.path.join(self.artifacts_dir, 'hello.txt')
        self.expected_contents = "Hello World"

        self.command_name = "lambda-builders-dev" if os.environ.get("LAMBDA_BUILDERS_DEV") else "lambda-builders"

        # Make sure the test workflow is in PYTHONPATH to be automatically loaded
        self.python_path_list = os.environ.get("PYTHONPATH", '').split(os.pathsep) + [self.TEST_WORKFLOWS_FOLDER]
        self.python_path = os.pathsep.join(filter(bool, self.python_path_list))

    def tearDown(self):
        shutil.rmtree(self.source_dir)
        shutil.rmtree(self.artifacts_dir)

    @parameterized.expand([
        ("request_through_stdin"),
        ("request_through_argument")
    ])
    def test_run_hello_workflow(self, flavor):

        request_json = json.dumps({
            "jsonschema": "2.0",
            "id": 1234,
            "method": "LambdaBuilder.build",
            "params": {
                "capability": {
                    "language": self.language,
                    "dependency_manager": self.dependency_manager,
                    "application_framework": self.application_framework
                },
                "supported_workflows": [self.HELLO_WORKFLOW_MODULE],
                "source_dir": self.source_dir,
                "artifacts_dir": self.artifacts_dir,
                "scratch_dir": "/ignored",
                "manifest_path": "/ignored",
                "runtime": "ignored",
                "optimizations": {},
                "options": {},
            }
        })

        env = copy.deepcopy(os.environ)
        env["PYTHONPATH"] = self.python_path

        stdout_data = None
        if flavor == "request_through_stdin":
            p = subprocess.Popen([self.command_name], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            stdout_data = p.communicate(input=request_json.encode('utf-8'))[0]
        elif flavor == "request_through_argument":
            p = subprocess.Popen([self.command_name, request_json], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            stdout_data = p.communicate()[0]
        else:
            raise ValueError("Invalid test flavor")

        # Validate the response object. It should be successful response
        response = json.loads(stdout_data)
        self.assertNotIn('error', response)
        self.assertIn('result', response)
        self.assertEquals(response['result']['artifacts_dir'], self.artifacts_dir)

        self.assertTrue(os.path.exists(self.expected_filename))
        contents = ''
        with open(self.expected_filename, 'r') as fp:
            contents = fp.read()

        self.assertEquals(contents, self.expected_contents)

