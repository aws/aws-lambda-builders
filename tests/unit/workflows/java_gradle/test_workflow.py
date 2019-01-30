from unittest import TestCase

from aws_lambda_builders.workflows.java_gradle.workflow import JavaGradleWorkflow
from aws_lambda_builders.workflows.java_gradle.actions import JavaGradleBuildAction, JavaGradleCopyArtifactsAction
from aws_lambda_builders.workflows.java_gradle.gradle_resolver import GradleResolver
from aws_lambda_builders.workflows.java_gradle.gradle_validator import GradleBinaryValidator


class TestJavaGradleWorkflow(TestCase):
    """
    the workflow requires an external utility (gradle) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_gradle_actions(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertEqual(len(workflow.actions), 2)

        self.assertIsInstance(workflow.actions[0], JavaGradleBuildAction)

        self.assertIsInstance(workflow.actions[1], JavaGradleCopyArtifactsAction)

    def test_workflow_sets_up_resolvers(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest")

        resolvers = workflow.get_resolvers()
        self.assertEqual(len(resolvers), 1)

        self.assertIsInstance(resolvers[0], GradleResolver)

    def test_workflow_sets_up_validators(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest")

        validators = workflow.get_validators()
        self.assertEqual(len(validators), 1)

        self.assertIsInstance(validators[0], GradleBinaryValidator)

    def test_no_options_workflow_creates_correct_mapping(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest")
        self.assertEqual(workflow.artifact_mapping, {'.': '.'})

    def test_no_artifact_mapping_option_workflow_creates_correct_mapping(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest", options={})
        self.assertEqual(workflow.artifact_mapping, {'.': '.'})

    def test_options_provided_workflow_creates_correct_mapping(self):
        artifact_mapping = {'lamda1': 'artifact1', 'lambda2': 'artfact2'}
        options = {'artifact_mapping': artifact_mapping}
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest", options=options)
        self.assertEqual(workflow.artifact_mapping, artifact_mapping)
