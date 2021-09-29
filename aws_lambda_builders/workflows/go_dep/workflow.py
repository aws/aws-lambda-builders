"""
Go Dep Workflow
"""

import logging
import os

from aws_lambda_builders.actions import CopySourceAction
from aws_lambda_builders.workflow import BaseWorkflow, Capability
from .actions import DepEnsureAction, GoBuildAction
from .utils import OSUtils
from .subproc_exec import SubprocessExec

LOG = logging.getLogger(__name__)


class GoDepWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build
    Go projects using `dep`
    """

    NAME = "GoDepBuilder"

    CAPABILITY = Capability(language="go", dependency_manager="dep", application_framework=None)

    EXCLUDED_FILES = (".aws-sam", ".git")

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, osutils=None, **kwargs):

        super(GoDepWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, **kwargs
        )

        options = kwargs["options"] if "options" in kwargs else {}
        handler = options.get("artifact_executable_name", None)

        if osutils is None:
            osutils = OSUtils()

        # project base name, where the Gopkg.toml and vendor dir are.
        base_dir = osutils.abspath(osutils.dirname(manifest_path))
        output_path = osutils.joinpath(osutils.abspath(artifacts_dir), handler)

        subprocess_dep = SubprocessExec(osutils, "dep")
        subprocess_go = SubprocessExec(osutils, "go")

        self.actions = [
            DepEnsureAction(base_dir, subprocess_dep),
            GoBuildAction(
                base_dir,
                osutils.abspath(source_dir),
                output_path,
                subprocess_go,
                self.architecture,
                env=osutils.environ,
            ),
        ]
