from unittest import TestCase

from aws_lambda_builders.workflows.java_maven.workflow import JavaMavenWorkflow
from aws_lambda_builders.workflows.java_maven.actions import \
    JavaMavenBuildAction, JavaMavenCopyArtifactsAction, JavaMavenCopyDependencyAction, JavaMavenCleanupAction
from aws_lambda_builders.workflows.java_maven.maven_resolver import MavenResolver
from aws_lambda_builders.workflows.java_maven.maven_validator import MavenValidator


class TestJavaMavenWorkflow(TestCase):
    """
    the workflow requires an external utility (maven) to run, so it is extensively tested in integration tests.
    this is just a quick wiring test to provide fast feedback if things are badly broken
    """

    def test_workflow_sets_up_maven_actions(self):
        workflow = JavaMavenWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], JavaMavenBuildAction)

        self.assertIsInstance(workflow.actions[1], JavaMavenCopyDependencyAction)

        self.assertIsInstance(workflow.actions[2], JavaMavenCopyArtifactsAction)

        self.assertIsInstance(workflow.actions[3], JavaMavenCleanupAction)

    def test_workflow_sets_up_resolvers(self):
        workflow = JavaMavenWorkflow("source", "artifacts", "scratch_dir", "manifest")

        resolvers = workflow.get_resolvers()
        self.assertEqual(len(resolvers), 1)

        self.assertIsInstance(resolvers[0], MavenResolver)

    def test_workflow_sets_up_validators(self):
        workflow = JavaMavenWorkflow("source", "artifacts", "scratch_dir", "manifest")

        validators = workflow.get_validators()
        self.assertEqual(len(validators), 1)

        self.assertIsInstance(validators[0], MavenValidator)
