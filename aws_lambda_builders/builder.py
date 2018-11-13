"""
Entrypoint for the AWS Lambda Builder library
"""

import importlib
import logging

from aws_lambda_builders.registry import get_workflow, DEFAULT_REGISTRY
from aws_lambda_builders.workflow import Capability

LOG = logging.getLogger(__name__)

_SUPPORTED_WORKFLOWS = [
    "aws_lambda_builders.workflows"
]


class LambdaBuilder(object):
    """
    Helps you build AWS Lambda functions. This class is the primary entry point for this library.
    """

    def __init__(self, language, dependency_manager, application_framework, supported_workflows=None):

        """
        Initialize the builder.
        :type supported_workflows: list
        :param supported_workflows:
            Optional list of workflow modules that should be loaded. By default we load all the workflows bundled
            with this library. This property is primarily used for testing. But in future it could be used to
            dynamically load user defined workflows.

            If set to None, we will load the default workflow modules.
            If set to empty list, we will **not** load any modules. Pass an empty list if the workflows
            were already loaded by the time this class is instantiated.

        :raises lambda_builders.exceptions.WorkflowNotFoundError: If a workflow for given capabilities is not found
        """

        # Load defaults if necessary. We check for `None` explicitly because callers could pass an empty list
        # if they do not want to load any modules. This supports the case where workflows are already loaded and
        # don't need to be loaded again.
        self.supported_workflows = _SUPPORTED_WORKFLOWS if supported_workflows is None else supported_workflows

        for workflow_module in self.supported_workflows:
            LOG.debug("Loading workflow module '%s'", workflow_module)

            # If a module is already loaded, this call is pretty much a no-op. So it is okay to keep loading again.
            importlib.import_module(workflow_module)

        self.capability = Capability(language=language,
                                     dependency_manager=dependency_manager,
                                     application_framework=application_framework)
        self.selected_workflow_cls = get_workflow(self.capability)
        LOG.debug("Found workflow '%s' to support capabilities '%s'", self.selected_workflow_cls.NAME, self.capability)

    def build(self, source_dir, artifacts_dir, scratch_dir, manifest_path,
              runtime=None, optimizations=None, options=None):
        """
        Actually build the code by running workflows

        :type source_dir: str
        :param source_dir:
            Path to a folder containing the source code

        :type artifacts_dir: str
        :param artifacts_dir:
            Path to a folder where the built artifacts should be placed

        :type scratch_dir: str
        :param scratch_dir:
            Path to a directory that the workflow can use as scratch space. Workflows are expected to use this directory
            to write temporary files instead of ``/tmp`` or other OS-specific temp directories.

        :type manifest_path: str
        :param manifest_path:
            Path to the dependency manifest

        :type runtime: str
        :param runtime:
            Optional, name of the AWS Lambda runtime that you are building for. This is sent to the builder for
            informational purposes.

        :type optimizations: dict
        :param optimizations:
            Optional dictionary of optimization flags to pass to the build action. **Not supported**.

        :type options: dict
        :param options:
            Optional dictionary of options ot pass to build action. **Not supported**.
        """

        workflow = self.selected_workflow_cls(source_dir,
                                              artifacts_dir,
                                              scratch_dir,
                                              manifest_path,
                                              runtime=runtime,
                                              optimizations=optimizations,
                                              options=options)

        return workflow.run()

    def _clear_workflows(self):
        DEFAULT_REGISTRY.clear()
