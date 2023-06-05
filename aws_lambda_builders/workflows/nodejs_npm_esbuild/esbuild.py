"""
Wrapper around calling esbuild through a subprocess.
"""
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Union

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.utils import OSUtils
from aws_lambda_builders.workflows.nodejs_npm_esbuild.exceptions import EsbuildCommandError, EsbuildExecutionError

LOG = logging.getLogger(__name__)


class SubprocessEsbuild(object):
    """
    Wrapper around the Esbuild command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, executable_search_paths, which):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type executable_search_paths: list
        :param executable_search_paths: List of paths to the NPM package binary utilities. This will
            be used to find embedded esbuild at runtime if present in the package

        :type which: aws_lambda_builders.utils.which
        :param which: Function to get paths which conform to the given mode on the PATH
            with the prepended additional search paths
        """
        self.osutils = osutils
        self.executable_search_paths = executable_search_paths
        self.which = which

    def esbuild_binary(self):
        """
        Finds the esbuild binary at runtime.

        The utility may be present as a package dependency of the Lambda project,
        or in the global path. If there is one in the Lambda project, it should
        be preferred over a global utility. The check has to be executed
        at runtime, since NPM dependencies will be installed by the workflow
        using one of the previous actions.
        """

        LOG.debug("checking for esbuild in: %s", self.executable_search_paths)
        binaries = self.which("esbuild", executable_search_paths=self.executable_search_paths)
        LOG.debug("potential esbuild binaries: %s", binaries)

        if binaries:
            return binaries[0]
        else:
            raise EsbuildExecutionError(
                message="Cannot find esbuild. esbuild must be installed on the host machine to use this feature. "
                "It is recommended to be installed on the PATH, "
                "but can also be included as a project dependency."
            )

    def run(self, args, cwd=None):
        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to Esbuild

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.nodejs_npm.npm.EsbuildExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if not args:
            raise ValueError("requires at least one arg")

        invoke_esbuild = [self.esbuild_binary()] + args

        LOG.debug("executing Esbuild: %s", invoke_esbuild)

        p = self.osutils.popen(invoke_esbuild, stdout=self.osutils.pipe, stderr=self.osutils.pipe, cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise EsbuildExecutionError(message=err.decode("utf8").strip())

        return out.decode("utf8").strip()


NON_CONFIGURABLE_VALUES = {"bundle", "platform", "outdir"}

# Ignore the values below. These are options that Lambda Builders accepts for
# Node.js related workflows, but are not relevant to esbuild itself.
ESBUILD_IGNORE_VALUES = {"use_npm_ci", "entry_points"}


class EsbuildCommandBuilder:
    ENTRY_POINTS = "entry_points"

    def __init__(
        self, scratch_dir: str, artifacts_dir: str, bundler_config: Dict[Any, Any], osutils: OSUtils, manifest: str
    ):
        self._scratch_dir = scratch_dir
        self._artifacts_dir = artifacts_dir
        self._bundler_config = bundler_config
        self._osutils = osutils
        self._manifest = manifest
        self._command: List[str] = []

    def get_command(self) -> List[str]:
        """
        Get all of the commands flags created by the command builder

        :rtype: List[str]
        :return: List of esbuild commands to be executed
        """
        return self._command

    def build_esbuild_args_from_config(self) -> "EsbuildCommandBuilder":
        """
        Build arguments configured in the command config (e.g. template.yaml)

        :rtype: EsbuildCommandBuilder
        :return: An instance of the command builder
        """
        args = []

        for config_key, config_value in self._bundler_config.items():
            if config_key in NON_CONFIGURABLE_VALUES:
                LOG.debug(
                    "'%s=%s' was not a used configuration since AWS Lambda Builders "
                    "sets these values for the code to be correctly consumed by AWS Lambda",
                    config_key,
                    config_value,
                )
                continue
            if config_key in ESBUILD_IGNORE_VALUES:
                continue
            configuration_type_callback = self._get_config_type_callback(config_value)
            LOG.debug("Configuring the parameter '%s=%s'", config_key, config_value)
            args.extend(configuration_type_callback(config_key, config_value))

        LOG.debug("Found the following args in the config: %s", str(args))

        self._command.extend(args)
        return self

    def _get_config_type_callback(
        self, config_value: Union[bool, str, list]
    ) -> Callable[[str, Union[bool, str, list]], List[str]]:
        """
        Determines the type of the command and returns the corresponding
        function to build out that command line argument type

        :param config_value: Union[bool, str, list]
            The configuration value configured through the options. The configuration should be one
            of the supported types as defined by the esbuild API  (https://esbuild.github.io/api/).
        :return: Callable[[str, Union[bool, str, list]], List[str]]
            Returns a function that the caller can use to turn the relevant
            configuration into the correctly formatted command line argument.
        """
        if isinstance(config_value, bool):
            return self._create_boolean_config
        elif isinstance(config_value, str):
            return self._create_str_config
        elif isinstance(config_value, list):
            return self._create_list_config
        raise EsbuildCommandError("Failed to determine the type of the configuration: %s", config_value)

    def _create_boolean_config(self, config_key: str, config_value: bool) -> List[str]:
        """
        Given boolean-type configuration, convert it to a string representation suitable for the esbuild API
        Should be created in the form ([--config-key])

        :param config_key: str
            The configuration key to be used
        :param config_value: bool
            The configuration value to be used
        :return: List[str]
            List of resolved command line arguments to be appended to the builder
        """
        if config_value is True:
            return [f"--{self._convert_snake_to_kebab_case(config_key)}"]
        return []

    def _create_str_config(self, config_key: str, config_value: str) -> List[str]:
        """
        Given string-type configuration, convert it to a string representation suitable for the esbuild API
        Should be created in the form ([--config-key=config_value])

        :param config_key: str
            The configuration key to be used
        :param config_value: List[str]
            The configuration value to be used
        :return: List[str]
            List of resolved command line arguments to be appended to the builder
        """
        return [f"--{self._convert_snake_to_kebab_case(config_key)}={config_value}"]

    def _create_list_config(self, config_key: str, config_value: List[str]) -> List[str]:
        """
        Given list-type configuration, convert it to a string representation suitable for the esbuild API
        Should be created in the form ([--config-key:config_value_a, --config_key:config_value_b])

        :param config_key: str
            The configuration key to be used
        :param config_value: List[str]
            The configuration value to be used
        :return: List[str]
            List of resolved command line arguments to be appended to the builder
        """
        args = []
        for config_item in config_value:
            args.append(f"--{self._convert_snake_to_kebab_case(config_key)}:{config_item}")
        return args

    def build_entry_points(self) -> "EsbuildCommandBuilder":
        """
        Build the entry points to the command

        :rtype: EsbuildCommandBuilder
        :return: An instance of the command builder
        """
        if self.ENTRY_POINTS not in self._bundler_config:
            raise EsbuildCommandError(f"{self.ENTRY_POINTS} not set ({self._bundler_config})")

        entry_points = self._bundler_config[self.ENTRY_POINTS]

        if not isinstance(entry_points, list):
            raise EsbuildCommandError(f"{self.ENTRY_POINTS} must be a list ({self._bundler_config})")

        if not entry_points:
            raise EsbuildCommandError(f"{self.ENTRY_POINTS} must not be empty ({self._bundler_config})")

        entry_paths = [self._osutils.joinpath(self._scratch_dir, entry_point) for entry_point in entry_points]

        LOG.debug("NODEJS building %s using esbuild to %s", entry_paths, self._artifacts_dir)

        for entry_path, entry_point in zip(entry_paths, entry_points):
            self._command.append(self._get_explicit_file_type(entry_point, entry_path))

        return self

    def build_default_values(self) -> "EsbuildCommandBuilder":
        """
        Build the default values that each call to esbuild should contain

        :rtype: EsbuildCommandBuilder
        :return: An instance of the command builder
        """
        args = ["--bundle", "--platform=node", "--outdir={}".format(self._artifacts_dir)]

        if "target" not in self._bundler_config:
            args.append("--target=es2020")

        if "format" not in self._bundler_config:
            args.append("--format=cjs")

        if "minify" not in self._bundler_config:
            args.append("--minify")

        LOG.debug("Using the following default args: %s", str(args))

        self._command.extend(args)
        return self

    def build_with_no_dependencies(self) -> "EsbuildCommandBuilder":
        """
        Set all dependencies located in the package.json to
        external so as to not bundle them with the source code

        :rtype: EsbuildCommandBuilder
        :return: An instance of the command builder
        """
        package = self._osutils.parse_json(self._manifest)
        dependencies = package.get("dependencies", {}).keys()
        args = ["--external:{}".format(dep) for dep in dependencies]
        self._command.extend(args)
        return self

    def _get_explicit_file_type(self, entry_point, entry_path):
        """
        Get an entry point with an explicit .ts or .js suffix.

        :type entry_point: str
        :param entry_point: path to entry file from code uri

        :type entry_path: str
        :param entry_path: full path of entry file

        :rtype: str
        :return: entry point with appropriate file extension

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """
        if Path(entry_point).suffix:
            if self._osutils.file_exists(entry_path):
                return entry_point
            raise ActionFailedError("entry point {} does not exist".format(entry_path))

        for ext in [".ts", ".js"]:
            entry_path_with_ext = entry_path + ext
            if self._osutils.file_exists(entry_path_with_ext):
                return entry_point + ext

        raise ActionFailedError("entry point {} does not exist".format(entry_path))

    @staticmethod
    def _convert_snake_to_kebab_case(arg: str) -> str:
        """
        The configuration properties passed down to Lambda Builders are done so using snake case
        e.g. "main_fields" but esbuild expects them using kebab-case "main-fields"

        :rtype: str
        :return: mutated string to match the esbuild argument format
        """
        return arg.replace("_", "-")
