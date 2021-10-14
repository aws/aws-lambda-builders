from unittest import TestCase

import hashlib
import os

from aws_lambda_builders.actions import CleanUpAction
from aws_lambda_builders.workflows.java.actions import JavaMoveDependenciesAction, JavaCopyDependenciesAction
from aws_lambda_builders.workflows.java_gradle.workflow import JavaGradleWorkflow
from aws_lambda_builders.workflows.java_gradle.actions import JavaGradleBuildAction, JavaGradleCopyArtifactsAction
from aws_lambda_builders.workflows.java_gradle.gradle_resolver import GradleResolver
from aws_lambda_builders.workflows.java_gradle.gradle_validator import GradleValidator
from aws_lambda_builders.architecture import ARM64


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
        self.assertIsInstance(validators[0], GradleValidator)

    def test_computes_correct_build_dir(self):
        workflow = JavaGradleWorkflow("source", "artifacts", "scratch_dir", "manifest")
        sha1 = hashlib.sha1()
        sha1.update(os.path.abspath(workflow.source_dir).encode("utf8"))
        expected_build_dir = os.path.join(workflow.scratch_dir, sha1.hexdigest())
        self.assertEqual(expected_build_dir, workflow.build_output_dir)

    def test_workflow_sets_up_gradle_actions_without_combine_dependencies(self):
        workflow = JavaGradleWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", combine_dependencies=False
        )

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], JavaGradleBuildAction)

        self.assertIsInstance(workflow.actions[1], JavaGradleCopyArtifactsAction)

        self.assertIsInstance(workflow.actions[2], CleanUpAction)

        self.assertIsInstance(workflow.actions[3], JavaMoveDependenciesAction)

    def test_workflow_sets_up_gradle_actions_with_combine_dependencies(self):
        workflow = JavaGradleWorkflow(
            "source", "artifacts", "scratch_dir", "manifest", dependencies_dir="dep", combine_dependencies=True
        )

        self.assertEqual(len(workflow.actions), 4)

        self.assertIsInstance(workflow.actions[0], JavaGradleBuildAction)

        self.assertIsInstance(workflow.actions[1], JavaGradleCopyArtifactsAction)

        self.assertIsInstance(workflow.actions[2], CleanUpAction)

        self.assertIsInstance(workflow.actions[3], JavaCopyDependenciesAction)

    def test_must_validate_architecture(self):
        workflow = JavaGradleWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
        )
        workflow_with_arm = JavaGradleWorkflow(
            "source",
            "artifacts",
            "scratch",
            "manifest",
            options={"artifact_executable_name": "foo"},
            architecture=ARM64,
        )

        self.assertEqual(workflow.architecture, "x86_64")
        self.assertEqual(workflow_with_arm.architecture, "arm64")
