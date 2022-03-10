"""
Wrapper around calling esbuild through a subprocess.
"""
from pathlib import Path

import logging

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm_esbuild.exceptions import EsbuildCommandError, EsbuildExecutionError

LOG = logging.getLogger(__name__)

# The esbuild API flags are broken up into three forms (https://esbuild.github.io/api/):
# Boolean types (--minify)
SUPPORTED_ESBUILD_APIS_BOOLEAN = [
    "minify",
    "sourcemap",
]

# single value types (--target=es2020)
SUPPORTED_ESBUILD_APIS_SINGLE_VALUE = [
    "target",
]

# Multi-value types (--external:axios --external:aws-sdk)
SUPPORTED_ESBUILD_APIS_MULTI_VALUE = [
    "external",
]


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
            raise EsbuildExecutionError(message="cannot find esbuild")

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


class EsbuildCommandBuilder:

    ENTRY_POINTS = "entry_points"

    def __init__(self, scratch_dir, artifacts_dir, bundler_config, osutils, manifest, use_dependency_layer=False):
        self.scratch_dir = scratch_dir
        self.artifacts_dir = artifacts_dir
        self.bundler_config = bundler_config
        self.manifest = manifest
        self.osutils = osutils
        self.use_dependency_layer = use_dependency_layer
        self.explicit_entry_points = []

    def get_esbuild_build_args(self):
        args = self.explicit_entry_points + ["--bundle", "--platform=node", "--format=cjs"]
        args.append("--outdir={}".format(self.artifacts_dir))
        args += self._set_default_values()

        if self.use_dependency_layer or "./node_modules/*" in self.bundler_config.get("external", []):
            if "external" in self.bundler_config:
                # Already marking everything as external
                self.bundler_config.pop("external")
            args += self._mark_all_external()

        args += self._get_boolean_args()
        args += self._get_single_value_args()
        args += self._get_multi_value_args()

        LOG.debug("Running: esbuild with args {}".format(str(args)))

        return args

    def set_and_validate_entry_points(self):
        if self.ENTRY_POINTS not in self.bundler_config:
            raise EsbuildCommandError(f"{self.ENTRY_POINTS} not set ({self.bundler_config})")

        entry_points = self.bundler_config[self.ENTRY_POINTS]

        if not isinstance(entry_points, list):
            raise EsbuildCommandError(f"{self.ENTRY_POINTS} must be a list ({self.bundler_config})")

        if not entry_points:
            raise EsbuildCommandError(f"{self.ENTRY_POINTS} must not be empty ({self.bundler_config})")

        entry_paths = [self.osutils.joinpath(self.scratch_dir, entry_point) for entry_point in entry_points]

        LOG.debug("NODEJS building %s using esbuild to %s", entry_paths, self.artifacts_dir)

        for entry_path, entry_point in zip(entry_paths, entry_points):
            self.explicit_entry_points.append(self._get_explicit_file_type(entry_point, entry_path))

    def _set_default_values(self):
        args = []

        if "target" not in self.bundler_config:
            args.append("--target=es2020")

        if "minify" not in self.bundler_config:
            args.append("--minify")

        if "sourcemap" not in self.bundler_config:
            args.append("--sourcemap")

        return args

    def _get_boolean_args(self):
        args = []
        for param in SUPPORTED_ESBUILD_APIS_BOOLEAN:
            if param in self.bundler_config and self.bundler_config[param] is True:
                args.append(f"--{param}")
        return args

    def _get_single_value_args(self):
        args = []
        for param in SUPPORTED_ESBUILD_APIS_SINGLE_VALUE:
            if param in self.bundler_config:
                val = self.bundler_config.get(param)
                args.append(f"--{param}={val}")
        return args

    def _get_multi_value_args(self):
        args = []
        for param in SUPPORTED_ESBUILD_APIS_MULTI_VALUE:
            if param in self.bundler_config:
                vals = self.bundler_config.get(param)
                if not isinstance(vals, list):
                    raise EsbuildCommandError(f"Invalid type for property {param}, must be a dict.")
                for param_item in vals:
                    args.append(f"--{param}:{param_item}")
        return args

    def _mark_all_external(self):
        package = self.osutils.parse_json(self.manifest)
        deps = package.get("dependencies", {}).keys()
        args = []
        for dep in deps:
            args.append("--external:{}".format(dep))
        return args

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
            if self.osutils.file_exists(entry_path):
                return entry_point
            raise ActionFailedError("entry point {} does not exist".format(entry_path))

        for ext in [".ts", ".js"]:
            entry_path_with_ext = entry_path + ext
            if self.osutils.file_exists(entry_path_with_ext):
                return entry_point + ext

        raise ActionFailedError("entry point {} does not exist".format(entry_path))
