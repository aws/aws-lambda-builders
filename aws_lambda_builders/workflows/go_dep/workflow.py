"""
Go Dep Workflow
"""

from aws_lambda_builders.workflow import BaseWorkflow, Capability


class GoDepWorkflow(BaseWorkflow):
    """
    A Lambda builder workflow that knows how to build
    Go projects using `dep`
    """

    NAME = "GoDepBuilder"

    CAPABILITY = Capability(language="go",
                            dependency_manager="dep",
                            application_framework=None)

    EXCLUDED_FILES = (".aws-sam")

    def __init__(self,
                source_dir,
                artifacts_dir,
                scratch_dir,
                manifest_path,
                runtime=None,
                osutils=None,
                **kwargs):

        super(GoDepWorkflow, self).__init__(source_dir,
                                            artifacts_dir,
                                            scratch_dir,
                                            manifest_path,
                                            runtime=runtime,
                                            **kwargs)
