"""
Actions specific to the esbuild bundler
"""
import logging
from tempfile import NamedTemporaryFile

from pathlib import Path

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .esbuild import EsbuildExecutionError

LOG = logging.getLogger(__name__)


class EsbuildBundleAction(BaseAction):

    """
    A Lambda Builder Action that packages a Node.js package using esbuild into a single file
    optionally transpiling TypeScript
    """

    NAME = "EsbuildBundle"
    DESCRIPTION = "Packaging source using Esbuild"
    PURPOSE = Purpose.COPY_SOURCE

    ENTRY_POINTS = "entry_points"

    def __init__(
        self,
        scratch_dir,
        artifacts_dir,
        bundler_config,
        osutils,
        subprocess_esbuild,
        subprocess_nodejs=None,
        skip_deps=False,
    ):
        """
        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper

        :type subprocess_nodejs: aws_lambda_builders.workflows.nodejs_npm_esbuild.node.SubprocessNodejs
        :param subprocess_nodejs: An instance of the nodejs process wrapper

        :type skip_deps: bool
        :param skip_deps: if dependencies should be omitted from bundling

        :type bundler_config: Dict[str,Any]
        :param bundler_config: the bundler configuration
        """
        super(EsbuildBundleAction, self).__init__()
        self.scratch_dir = scratch_dir
        self.artifacts_dir = artifacts_dir
        self.bundler_config = bundler_config
        self.osutils = osutils
        self.subprocess_esbuild = subprocess_esbuild
        self.skip_deps = skip_deps
        self.subprocess_nodejs = subprocess_nodejs

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """

        explicit_entry_points = self._construct_esbuild_entry_points()

        args = explicit_entry_points + ["--bundle", "--platform=node", "--format=cjs"]
        minify = self.bundler_config.get("minify", True)
        sourcemap = self.bundler_config.get("sourcemap", True)
        target = self.bundler_config.get("target", "es2020")
        external = self.bundler_config.get("external", [])
        loader = self.bundler_config.get("loader", [])
        if minify:
            args.append("--minify")
        if sourcemap:
            args.append("--sourcemap")
        if external:
            args.extend(map(lambda x: f"--external:{x}", external))
        if loader:
            args.extend(map(lambda x: f"--loader:{x}", loader))

        args.append("--target={}".format(target))
        args.append("--outdir={}".format(self.artifacts_dir))

        if self.skip_deps:
            LOG.info("Running custom esbuild using Node.js")
            # Don't pass externals because the esbuild.js template makes everything external
            script = EsbuildBundleAction._get_node_esbuild_template(
                explicit_entry_points, target, self.artifacts_dir, minify, sourcemap
            )
            self._run_external_esbuild_in_nodejs(script)
            return

        try:
            self.subprocess_esbuild.run(args, cwd=self.scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))

    def _run_external_esbuild_in_nodejs(self, script):
        """
        Run esbuild in a separate process through Node.js
        Workaround for https://github.com/evanw/esbuild/issues/1958

        :type script: str
        :param script: Node.js script to execute

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """
        with NamedTemporaryFile(dir=self.scratch_dir, mode="w") as tmp:
            tmp.write(script)
            tmp.flush()
            try:
                self.subprocess_nodejs.run([tmp.name], cwd=self.scratch_dir)
            except EsbuildExecutionError as ex:
                raise ActionFailedError(str(ex))

    def _construct_esbuild_entry_points(self):
        """
        Construct the list of explicit entry points
        """
        if self.ENTRY_POINTS not in self.bundler_config:
            raise ActionFailedError(f"{self.ENTRY_POINTS} not set ({self.bundler_config})")

        entry_points = self.bundler_config[self.ENTRY_POINTS]

        if not isinstance(entry_points, list):
            raise ActionFailedError(f"{self.ENTRY_POINTS} must be a list ({self.bundler_config})")

        if not entry_points:
            raise ActionFailedError(f"{self.ENTRY_POINTS} must not be empty ({self.bundler_config})")

        entry_paths = [self.osutils.joinpath(self.scratch_dir, entry_point) for entry_point in entry_points]

        LOG.debug("NODEJS building %s using esbuild to %s", entry_paths, self.artifacts_dir)

        explicit_entry_points = []
        for entry_path, entry_point in zip(entry_paths, entry_points):
            explicit_entry_points.append(self._get_explicit_file_type(entry_point, entry_path))
        return explicit_entry_points

    @staticmethod
    def _get_node_esbuild_template(entry_points, target, out_dir, minify, sourcemap):
        """
        Get the esbuild nodejs plugin template

        :type entry_points: List[str]
        :param entry_points: list of entry points

        :type target: str
        :param target: target version

        :type out_dir: str
        :param out_dir: output directory to bundle into

        :type minify: bool
        :param minify: if bundled code should be minified

        :type sourcemap: bool
        :param sourcemap: if esbuild should produce a sourcemap

        :rtype: str
        :return: formatted template
        """
        curr_dir = Path(__file__).resolve().parent
        with open(str(Path(curr_dir, "esbuild-plugin.js.template")), "r") as f:
            input_str = f.read()
            result = input_str.format(
                target=target,
                minify="true" if minify else "false",
                sourcemap="true" if sourcemap else "false",
                out_dir=repr(out_dir),
                entry_points=entry_points,
            )
        return result

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


class EsbuildCheckVersionAction(BaseAction):
    """
    A Lambda Builder Action that verifies that esbuild is a version supported by sam accelerate
    """

    NAME = "EsbuildCheckVersion"
    DESCRIPTION = "Checking esbuild version"
    PURPOSE = Purpose.COMPILE_SOURCE

    MIN_VERSION = "0.14.13"

    def __init__(self, scratch_dir, subprocess_esbuild):
        """
        :type scratch_dir: str
        :param scratch_dir: temporary directory where esbuild is executed

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm_esbuild.esbuild.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper
        """
        super().__init__()
        self.scratch_dir = scratch_dir
        self.subprocess_esbuild = subprocess_esbuild

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild version checking fails
        """
        args = ["--version"]

        try:
            version = self.subprocess_esbuild.run(args, cwd=self.scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))

        LOG.debug("Found esbuild with version: %s", version)

        try:
            check_version = EsbuildCheckVersionAction._get_version_tuple(self.MIN_VERSION)
            esbuild_version = EsbuildCheckVersionAction._get_version_tuple(version)

            if esbuild_version < check_version:
                raise ActionFailedError(
                    f"Unsupported esbuild version. To use a dependency layer, the esbuild version must be at "
                    f"least {self.MIN_VERSION}. Version found: {version}"
                )
        except (TypeError, ValueError) as ex:
            raise ActionFailedError(f"Unable to parse esbuild version: {str(ex)}")

    @staticmethod
    def _get_version_tuple(version_string):
        """
        Get an integer tuple representation of the version for comparison

        :type version_string: str
        :param version_string: string containing the esbuild version

        :rtype: tuple
        :return: version tuple used for comparison
        """
        return tuple(map(int, version_string.split(".")))
