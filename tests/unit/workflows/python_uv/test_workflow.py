import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized, parameterized_class

from aws_lambda_builders.actions import CleanUpAction, CopyDependenciesAction, CopySourceAction
from aws_lambda_builders.exceptions import WorkflowFailedError
from aws_lambda_builders.workflows.python_uv.actions import PythonUvBuildAction
from aws_lambda_builders.workflows.python_uv.utils import EXPERIMENTAL_FLAG_BUILD_PERFORMANCE, OSUtils
from aws_lambda_builders.workflows.python_uv.workflow import PythonUvWorkflow


@parameterized_class(
    ("experimental_flags",),
    [
        ([]),
        ([EXPERIMENTAL_FLAG_BUILD_PERFORMANCE]),
    ],
)
class TestPythonUvWorkflow(TestCase):
    experimental_flags = []

    def setUp(self):
        self.osutils = OSUtils()
        self.osutils_mock = Mock(spec=self.osutils)
        self.osutils_mock.file_exists.return_value = True
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )
        self.python_major_version = "3"
        self.python_minor_version = "9"
        self.language = "python"

    def test_workflow_sets_up_actions(self):
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertIsInstance(self.workflow.actions[0], PythonUvBuildAction)
        self.assertIsInstance(self.workflow.actions[1], CopySourceAction)

    def test_workflow_sets_up_actions_without_requirements(self):
        self.osutils_mock.file_exists.return_value = False
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_sets_up_actions_with_dependencies_dir(self):
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            dependencies_dir="deps",
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 4)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonUvBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopyDependenciesAction)
        self.assertIsInstance(self.workflow.actions[3], CopySourceAction)

        # Dependencies are installed into dependencies_dir, then copied into artifacts_dir;
        # artifact_dir is the copy source and dest_dir the destination (must not be swapped).
        copy_deps_action = self.workflow.actions[2]
        self.assertEqual(copy_deps_action.source_dir, "source")
        self.assertEqual(copy_deps_action.artifact_dir, "deps")
        self.assertEqual(copy_deps_action.dest_dir, "artifacts")

    def test_workflow_sets_up_actions_without_download_dependencies_and_dependencies_dir(self):
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            download_dependencies=False,
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 1)
        self.assertIsInstance(self.workflow.actions[0], CopySourceAction)

    def test_workflow_sets_up_actions_without_combine_dependencies(self):
        self.workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            dependencies_dir="deps",
            combine_dependencies=False,
            experimental_flags=self.experimental_flags,
        )

        self.assertEqual(len(self.workflow.actions), 3)
        self.assertIsInstance(self.workflow.actions[0], CleanUpAction)
        self.assertIsInstance(self.workflow.actions[1], PythonUvBuildAction)
        self.assertIsInstance(self.workflow.actions[2], CopySourceAction)

    def test_workflow_name(self):
        self.assertEqual(self.workflow.NAME, "PythonUvBuilder")

    def test_workflow_capability(self):
        self.assertEqual(self.workflow.CAPABILITY.language, "python")
        self.assertEqual(self.workflow.CAPABILITY.dependency_manager, "uv")
        self.assertEqual(self.workflow.CAPABILITY.application_framework, None)

    def test_workflow_excluded_files(self):
        expected_excluded_files = (
            ".aws-sam",
            ".chalice",
            ".git",
            ".gitignore",
            "*.pyc",
            "__pycache__",
            "*.so",
            ".Python",
            "*.egg-info",
            "*.egg",
            "pip-log.txt",
            "pip-delete-this-directory.txt",
            "htmlcov",
            ".tox",
            ".nox",
            ".coverage",
            ".cache",
            ".pytest_cache",
            ".python-version",
            ".mypy_cache",
            ".dmypy.json",
            ".pyre",
            ".env",
            ".venv",
            "venv",
            "venv.bak",
            "env.bak",
            "ENV",
            "env",
            ".uv-cache",
            "uv.lock.bak",
            ".vscode",
            ".idea",
        )
        self.assertEqual(self.workflow.EXCLUDED_FILES, expected_excluded_files)

    def test_get_resolvers(self):
        # UV has built-in Python version handling, no external resolvers needed
        resolvers = self.workflow.get_resolvers()
        self.assertEqual(len(resolvers), 0)

    def test_get_validators(self):
        validators = self.workflow.get_validators()
        # UV has built-in Python version handling, no external validators needed
        self.assertEqual(len(validators), 0)

    @patch("aws_lambda_builders.workflows.python_uv.workflow.detect_uv_manifest")
    def test_workflow_auto_detects_manifest(self, mock_detect):
        mock_detect.return_value = "/path/to/pyproject.toml"
        self.osutils_mock.file_exists.return_value = False  # Original manifest doesn't exist

        workflow = PythonUvWorkflow(
            "source",
            "artifacts",
            "scratch_dir",
            "nonexistent_manifest",
            runtime="python3.9",
            osutils=self.osutils_mock,
            experimental_flags=self.experimental_flags,
        )

        mock_detect.assert_called_once_with("source")
        # Should have UV build action since manifest was detected
        self.assertEqual(len(workflow.actions), 2)
        self.assertIsInstance(workflow.actions[0], PythonUvBuildAction)


class TestPythonUvWorkflowBuildOptions(TestCase):
    def setUp(self):
        self.source_dir = tempfile.mkdtemp()
        self.pyproject = os.path.join(self.source_dir, "pyproject.toml")
        self._write_pyproject('[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n')
        # Keep a developer's own UV_COMPILE_BYTECODE out of these tests
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("UV_COMPILE_BYTECODE", None)

    def tearDown(self):
        shutil.rmtree(self.source_dir)

    def _write_pyproject(self, extra=""):
        with open(self.pyproject, "w") as f:
            f.write('[project]\nname = "app"\nversion = "0.1.0"\n' + extra)

    def _workflow(self, options, manifest=None, **kwargs):
        return PythonUvWorkflow(
            self.source_dir,
            "artifacts",
            "scratch_dir",
            manifest or self.pyproject,
            runtime="python3.12",
            options=options,
            **kwargs,
        )

    def test_options_are_passed_to_the_build_action(self):
        workflow = self._workflow(
            {
                "build_logical_id": "Fn",
                "uv_groups": ["lambda"],
                "uv_extras": ["fast"],
                "uv_prune": ["boto3"],
            }
        )
        config = workflow.actions[0].config
        self.assertEqual(config.groups, ["lambda"])
        self.assertEqual(config.extras, ["fast"])
        self.assertFalse(config.all_extras)
        self.assertEqual(config.prune, ["boto3"])
        self.assertFalse(config.compile_bytecode)

    def test_compile_bytecode_option_is_passed_to_the_build_action(self):
        config = self._workflow({"uv_compile_bytecode": True}).actions[0].config
        self.assertTrue(config.compile_bytecode)

    def test_compile_bytecode_on_requirements_build_is_allowed(self):
        requirements = os.path.join(self.source_dir, "requirements.txt")
        open(requirements, "w").close()
        config = self._workflow({"uv_compile_bytecode": True}, manifest=requirements).actions[0].config
        self.assertTrue(config.compile_bytecode)

    def test_export_option_with_compile_bytecode_on_requirements_build_fails(self):
        requirements = os.path.join(self.source_dir, "requirements.txt")
        open(requirements, "w").close()
        with self.assertRaises(WorkflowFailedError) as ctx:
            self._workflow({"uv_groups": ["lambda"], "uv_compile_bytecode": True}, manifest=requirements)
        self.assertIn("Build options uv_groups need a pyproject.toml project", str(ctx.exception))

    @parameterized.expand([("1",), ("true",), ("YES",), ("On",), ("y",), ("t",)])
    def test_truthy_env_enables_compile_bytecode_without_option(self, value):
        os.environ["UV_COMPILE_BYTECODE"] = value
        with self.assertLogs("aws_lambda_builders.workflows.python_uv.workflow", "INFO") as logs:
            config = self._workflow(None).actions[0].config
        self.assertTrue(config.compile_bytecode)
        self.assertIn(f"UV_COMPILE_BYTECODE={value} is set", "\n".join(logs.output))

    def test_truthy_env_enables_compile_bytecode_on_requirements_build(self):
        os.environ["UV_COMPILE_BYTECODE"] = "1"
        requirements = os.path.join(self.source_dir, "requirements.txt")
        open(requirements, "w").close()
        config = self._workflow({"build_logical_id": "Fn"}, manifest=requirements).actions[0].config
        self.assertTrue(config.compile_bytecode)

    def test_explicit_false_option_wins_over_truthy_env(self):
        os.environ["UV_COMPILE_BYTECODE"] = "1"
        config = self._workflow({"uv_compile_bytecode": False}).actions[0].config
        self.assertFalse(config.compile_bytecode)

    @parameterized.expand([("0",), ("false",), ("OFF",), ("no",), ("n",), ("f",)])
    def test_falsy_env_keeps_compile_bytecode_off(self, value):
        os.environ["UV_COMPILE_BYTECODE"] = value
        with self.assertNoLogs("aws_lambda_builders.workflows.python_uv.workflow", "INFO"):
            config = self._workflow(None).actions[0].config
        self.assertFalse(config.compile_bytecode)

    @parameterized.expand([("2",), ("maybe",), ("",)])
    def test_unknown_env_value_warns_and_keeps_compile_bytecode_off(self, value):
        os.environ["UV_COMPILE_BYTECODE"] = value
        with self.assertLogs("aws_lambda_builders.workflows.python_uv.workflow", "WARNING") as logs:
            config = self._workflow(None).actions[0].config
        self.assertFalse(config.compile_bytecode)
        self.assertIn(f"Ignoring UV_COMPILE_BYTECODE={value!r}", "\n".join(logs.output))

    def test_no_options_keep_defaults(self):
        config = self._workflow(None).actions[0].config
        self.assertEqual(config.to_export_args(), [])
        self.assertFalse(config.compile_bytecode)

    @parameterized.expand(
        [
            ({"uv_groups": "lambda"}, "uv_groups must be a list of non-empty strings"),
            ({"uv_extras": ["ok", 1]}, "uv_extras must be a list of non-empty strings"),
            ({"uv_groups": [""]}, "uv_groups must be a list of non-empty strings"),
            ({"uv_all_extras": "true"}, "uv_all_extras must be true or false"),
            ({"uv_prune": "boto3"}, "uv_prune must be a list of non-empty strings"),
            ({"uv_prune": [""]}, "uv_prune must be a list of non-empty strings"),
            ({"uv_compile_bytecode": "true"}, "uv_compile_bytecode must be true or false"),
            ({"uv_compile_bytecode": 1}, "uv_compile_bytecode must be true or false"),
            ({"uv_group": ["lambda"]}, "Unknown uv build option(s): uv_group"),
            ({"uv_extras": ["x"], "uv_all_extras": True}, "uv_extras and uv_all_extras cannot be used together"),
        ]
    )
    def test_invalid_options_fail(self, options, message):
        with self.assertRaises(WorkflowFailedError) as ctx:
            self._workflow(options)
        self.assertTrue(str(ctx.exception).startswith("PythonUvBuilder:Validation - "), str(ctx.exception))
        self.assertIn(message, str(ctx.exception))

    def test_options_on_requirements_build_fail(self):
        requirements = os.path.join(self.source_dir, "requirements.txt")
        open(requirements, "w").close()
        with self.assertRaises(WorkflowFailedError) as ctx:
            self._workflow({"uv_groups": ["lambda"]}, manifest=requirements)
        self.assertIn(
            "uv_groups need a pyproject.toml project, but this build uses requirements.txt", str(ctx.exception)
        )

    def test_prune_on_requirements_build_fails(self):
        requirements = os.path.join(self.source_dir, "requirements.txt")
        open(requirements, "w").close()
        with self.assertRaises(WorkflowFailedError) as ctx:
            self._workflow({"uv_prune": ["boto3"]}, manifest=requirements)
        self.assertIn("uv_prune need a pyproject.toml project", str(ctx.exception))

    def test_default_valued_options_on_requirements_build_are_allowed(self):
        requirements = os.path.join(self.source_dir, "requirements.txt")
        open(requirements, "w").close()
        workflow = self._workflow({"uv_groups": [], "uv_all_extras": False}, manifest=requirements)
        self.assertIsInstance(workflow.actions[0], PythonUvBuildAction)
