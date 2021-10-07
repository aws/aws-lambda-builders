from unittest import TestCase

from aws_lambda_builders.workflows.java.actions import JavaCopyDependenciesAction, JavaMoveDependenciesAction
from aws_lambda_builders.workflows.java_maven.workflow import JavaMavenWorkflow
from aws_lambda_builders.workflows.java_maven.actions import (
    JavaMavenBuildAction,
    JavaMavenCopyArtifactsAction,
    JavaMavenCopyDependencyAction,
)
from aws_lambda_builders.actions import CopySourceAction
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

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

        self.assertIsInstance(workflow.actions[1], JavaMavenBuildAction)

        self.assertIsInstance(workflow.actions[2], JavaMavenCopyDependencyAction)

        self.assertIsInstance(workflow.actions[3], JavaMavenCopyArtifactsAction)

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

    def test_workflow_excluded_files(self):
        workflow = JavaMavenWorkflow("source", "artifacts", "scratch_dir", "manifest")

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

        self.assertEqual(".aws-sam", workflow.actions[0].excludes[0])

        self.assertEqual(".git", workflow.actions[0].excludes[1])

    def test_workflow_sets_up_maven_actions_without_combine_dependencies(self):
        workflow = JavaMavenWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", combine_dependencies=False
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

        self.assertIsInstance(workflow.actions[1], JavaMavenBuildAction)

        self.assertIsInstance(workflow.actions[2], JavaMavenCopyDependencyAction)

        self.assertIsInstance(workflow.actions[3], JavaMavenCopyArtifactsAction)

        self.assertIsInstance(workflow.actions[4], JavaMoveDependenciesAction)

    def test_workflow_sets_up_maven_actions_with_combine_dependencies(self):
        workflow = JavaMavenWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", combine_dependencies=True
        )

        self.assertEqual(len(workflow.actions), 5)

        self.assertIsInstance(workflow.actions[0], CopySourceAction)

        self.assertIsInstance(workflow.actions[1], JavaMavenBuildAction)

        self.assertIsInstance(workflow.actions[2], JavaMavenCopyDependencyAction)

        self.assertIsInstance(workflow.actions[3], JavaMavenCopyArtifactsAction)

        self.assertIsInstance(workflow.actions[4], JavaCopyDependenciesAction)
