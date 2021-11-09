"""
.NET Core CLI Package Workflow
"""
from aws_lambda_builders.workflow import BaseWorkflow, Capability

from .actions import GlobalToolInstallAction, RunPackageAction
from .dotnetcli import SubprocessDotnetCLI
from .dotnetcli_resolver import DotnetCliResolver
from .utils import OSUtils


class DotnetCliPackageWorkflow(BaseWorkflow):

    """
    A Lambda builder workflow that knows to build and package .NET Core Lambda functions
    """

    NAME = "DotnetCliPackageBuilder"

    CAPABILITY = Capability(language="dotnet", dependency_manager="cli-package", application_framework=None)

    def __init__(self, source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, mode=None, **kwargs):

        super(DotnetCliPackageWorkflow, self).__init__(
            source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=runtime, mode=mode, **kwargs
        )

        options = kwargs["options"] if "options" in kwargs else {}
        subprocess_dotnetcli = SubprocessDotnetCLI(os_utils=OSUtils())
        dotnetcli_install = GlobalToolInstallAction(subprocess_dotnet=subprocess_dotnetcli)

        dotnetcli_deployment = RunPackageAction(
            source_dir,
            subprocess_dotnet=subprocess_dotnetcli,
            artifacts_dir=artifacts_dir,
            options=options,
            mode=mode,
            architecture=self.architecture,
        )
        self.actions = [dotnetcli_install, dotnetcli_deployment]

    def get_resolvers(self):
        return [DotnetCliResolver(executable_search_paths=self.executable_search_paths)]
