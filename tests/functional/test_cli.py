
import json
import os
import shutil
import tempfile
import subprocess
import copy

from unittest import TestCase


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
        self.python_path_list = os.environ.get("PYTHONPATH", '').split(os.pathsep) + [self.TEST_WORKFLOWS_FOLDER]
        self.python_path = os.pathsep.join(filter(bool, self.python_path_list))
        print(self.python_path)

    def tearDown(self):
        shutil.rmtree(self.source_dir)
        shutil.rmtree(self.artifacts_dir)

    def test_run_hello_workflow(self):

        request_json = json.dumps({
            "jsonschema": "2.0",
            "id": 1234,
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
                "optimizations": {},
                "options": {},
            }
        }).encode('utf-8')

        env = copy.deepcopy(os.environ)
        env["PYTHONPATH"] = self.python_path

        p = subprocess.Popen([self.command_name], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout_data = p.communicate(input=request_json)[0]
        print(stdout_data)

        self.assertTrue(os.path.exists(self.expected_filename))
        contents = ''
        with open(self.expected_filename, 'r') as fp:
            contents = fp.read()

        self.assertEquals(contents, self.expected_contents)

