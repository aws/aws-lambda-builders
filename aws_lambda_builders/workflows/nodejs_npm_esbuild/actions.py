"""
Actions specific to the esbuild bundler
"""
import logging
import shutil

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

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper
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

        args = explicit_entry_points + ["--bundle", "--platform=node", "--format=cjs"]
        minify = self.bundler_config.get("minify", True)
        sourcemap = self.bundler_config.get("sourcemap", True)
        target = self.bundler_config.get("target", "es2020")
        if minify:
            args.append("--minify")
        if sourcemap:
            args.append("--sourcemap")
        args.append("--target={}".format(target))
        args.append("--outdir={}".format(self.artifacts_dir))

        if self.skip_deps:
            LOG.debug("Running custom esbuild using Node.js")
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
        bundle_config_filename = "bundle-scratch.js"
        args = [bundle_config_filename]
        bundle_file = Path(self.scratch_dir, bundle_config_filename)

        with open(bundle_file, "a") as file:
            file.write(script)

        try:
            self.subprocess_nodejs.run(args, cwd=self.scratch_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))

    @staticmethod
    def _get_node_esbuild_template(entry_points, target, out_dir, minify, sourcemap):
        # pylint: disable=W1401
        minify_node = "true" if minify else "false"
        sourcemap_node = "true" if sourcemap else "false"
        return f"""
                let skipBundleNodeModules = {{
                  name: 'make-all-packages-external',
                  setup(build) {{
                    let filter = /^[^.\/]|^\.[^.\/]|^\.\.[^\/]/ // Must not start with "/" or "./" or "../"
                    build.onResolve({{ filter }}, args => ({{ path: args.path, external: true }}))
                  }},
                }}

                require('esbuild').build({{
                  entryPoints: {entry_points},
                  bundle: true,
                  platform: 'node',
                  format: 'cjs',
                  sourcemap: {sourcemap_node},
                  target: '{target}',
                  outdir: '{out_dir}',
                  minify: {minify_node},
                  plugins: [skipBundleNodeModules],
                }}).catch(() => process.exit(1))
                """

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


class EsbuildMoveBundledArtifactsAction(BaseAction):

    NAME = "EsbuildMoveBundledArtifactsAction"
    DESCRIPTION = "Move bundled artifacts from scratch dir to artifacts dir"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, bundler_config, scratch_dir, artifacts_dir):
        self.bundler_config = bundler_config
        self.scratch_dir = scratch_dir
        self.artifacts_dir = artifacts_dir

    def execute(self):

        if not Path(self.artifacts_dir).exists():
            Path(self.artifacts_dir).mkdir(parents=True, exist_ok=False)

        entry_points = self.bundler_config.get("entry_points")
        for entry_point in entry_points:
            artifact = entry_point + ".js"
            source_path = str(Path(self.scratch_dir, artifact))
            shutil.move(source_path, self.artifacts_dir)
            if self.bundler_config.get("sourcemap", False):
                source_map = artifact + ".map"
                source_map_path = str(Path(self.scratch_dir, source_map))
                shutil.move(source_map_path, self.artifacts_dir)


class EsbuildCheckVersionAction(BaseAction):
    """
    A Lambda Builder Action that verifies that esbuild is a version supported by sam accelerate
    """

    NAME = "EsbuildCheckVersion"
    DESCRIPTION = "Checking esbuild version"
    PURPOSE = Purpose.COMPILE_SOURCE

    MIN_VERSION = "0.14.13"

    def __init__(self, scratch_dir, subprocess_esbuild):
        self.scratch_dir = scratch_dir
        self.subprocess_esbuild = subprocess_esbuild

    def execute(self):
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
        return tuple(map(int, version_string.split(".")))
