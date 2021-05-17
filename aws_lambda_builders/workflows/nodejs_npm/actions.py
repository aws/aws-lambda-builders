"""
Action to resolve NodeJS dependencies using NPM
"""

import logging

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .npm import NpmExecutionError
from .esbuild import EsbuildExecutionError

LOG = logging.getLogger(__name__)


class NodejsNpmPackAction(BaseAction):

    """
    A Lambda Builder Action that packages a Node.js package using NPM to extract the source and remove test resources
    """

    NAME = "NpmPack"
    DESCRIPTION = "Packaging source using NPM"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, artifacts_dir, scratch_dir, manifest_path, osutils, subprocess_npm):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type manifest_path: str
        :param manifest_path: path to package.json of an NPM project with the source to pack

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper
        """
        super(NodejsNpmPackAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.osutils = osutils
        self.subprocess_npm = subprocess_npm

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM packaging fails
        """
        try:
            package_path = "file:{}".format(self.osutils.abspath(self.osutils.dirname(self.manifest_path)))

            LOG.debug("NODEJS packaging %s to %s", package_path, self.scratch_dir)

            tarfile_name = self.subprocess_npm.run(["pack", "-q", package_path], cwd=self.scratch_dir).splitlines()[-1]

            LOG.debug("NODEJS packed to %s", tarfile_name)

            tarfile_path = self.osutils.joinpath(self.scratch_dir, tarfile_name)

            LOG.debug("NODEJS extracting to %s", self.artifacts_dir)

            self.osutils.extract_tarfile(tarfile_path, self.artifacts_dir)

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmInstallAction(BaseAction):

    """
    A Lambda Builder Action that installs NPM project dependencies
    """

    NAME = "NpmInstall"
    DESCRIPTION = "Installing dependencies from NPM"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, subprocess_npm):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory with project source files.
            Dependencies will be installed in this directory.

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper
        """

        super(NodejsNpmInstallAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.subprocess_npm = subprocess_npm

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """

        try:
            LOG.debug("NODEJS installing in: %s", self.artifacts_dir)

            self.subprocess_npm.run(
                ["install", "-q", "--no-audit", "--no-save", "--production", "--unsafe-perm"], cwd=self.artifacts_dir
            )

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmCIAction(BaseAction):

    """
    A Lambda Builder Action that installs NPM project dependencies
    using the CI method - which is faster and better reproducible
    for CI environments, but requires a lockfile (package-lock.json
    or npm-shrinkwrap.json)
    """

    NAME = "NpmCI"
    DESCRIPTION = "Installing dependencies from NPM using the CI method"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, subprocess_npm):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory with project source files.
            Dependencies will be installed in this directory.

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper
        """

        super(NodejsNpmCIAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.subprocess_npm = subprocess_npm

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """

        try:
            LOG.debug("NODEJS installing ci in: %s", self.artifacts_dir)

            self.subprocess_npm.run(
                ["ci"], cwd=self.artifacts_dir
            )

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmrcCopyAction(BaseAction):

    """
    A Lambda Builder Action that copies NPM config file .npmrc
    """

    NAME = "CopyNpmrc"
    DESCRIPTION = "Copying configuration from .npmrc"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, artifacts_dir, source_dir, osutils):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory with project source files.
            Dependencies will be installed in this directory.

        :type source_dir: str
        :param source_dir: directory containing project source files.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation
        """

        super(NodejsNpmrcCopyAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.source_dir = source_dir
        self.osutils = osutils

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when .npmrc copying fails
        """

        try:
            npmrc_path = self.osutils.joinpath(self.source_dir, ".npmrc")
            if self.osutils.file_exists(npmrc_path):
                LOG.debug(".npmrc copying in: %s", self.artifacts_dir)
                self.osutils.copy_file(npmrc_path, self.artifacts_dir)

        except OSError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmrcCleanUpAction(BaseAction):

    """
    A Lambda Builder Action that cleans NPM config file .npmrc
    """

    NAME = "CleanUpNpmrc"
    DESCRIPTION = "Cleans artifacts dir"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, artifacts_dir, osutils):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory with project source files.
            Dependencies will be installed in this directory.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation
        """

        super(NodejsNpmrcCleanUpAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.osutils = osutils

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when deleting .npmrc fails
        """

        try:
            npmrc_path = self.osutils.joinpath(self.artifacts_dir, ".npmrc")
            if self.osutils.file_exists(npmrc_path):
                LOG.debug(".npmrc cleanup in: %s", self.artifacts_dir)
                self.osutils.remove_file(npmrc_path)

        except OSError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmLockFileCleanUpAction(BaseAction):

    """
    A Lambda Builder Action that cleans up garbage lockfile left by 7 in node_modules
    """

    NAME = "LockfileCleanUp"
    DESCRIPTION = "Cleans garbage lockfiles dir"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, artifacts_dir, osutils):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory with project source files.
            Dependencies will be installed in this directory.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation
        """

        super(NodejsNpmLockFileCleanUpAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.osutils = osutils

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when deleting the lockfile fails
        """

        try:
            npmrc_path = self.osutils.joinpath(self.artifacts_dir, "node_modules", ".package-lock.json")
            if self.osutils.file_exists(npmrc_path):
                LOG.debug(".package-lock cleanup in: %s", self.artifacts_dir)
                self.osutils.remove_file(npmrc_path)

        except OSError as ex:
            raise ActionFailedError(str(ex))


class EsbuildBundleAction(BaseAction):

    """
    A Lambda Builder Action that packages a Node.js package using esbuild into a single file
    optionally transpiling TypeScript
    """

    NAME = "EsbuildBundle"
    DESCRIPTION = "Packaging source using Esbuild"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, artifacts_dir, bundler_config, osutils, subprocess_esbuild):
        """
        :type source_dir: str
        :param source_dir: an existing (readable) directory containing source files


        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_esbuild: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessEsbuild
        :param subprocess_esbuild: An instance of the Esbuild process wrapper
        """
        super(EsbuildBundleAction, self).__init__()
        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.bundler_config = bundler_config
        self.osutils = osutils
        self.subprocess_esbuild = subprocess_esbuild

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when esbuild packaging fails
        """

        if 'main' not in self.bundler_config:
            raise ActionFailedError("main entry point not set %s" % self.bundler_config)

        entrypoint = self.bundler_config['main']
        entrypath = self.osutils.joinpath(self.source_dir, entrypoint)
        LOG.debug("NODEJS bunlding %s using esbuild to %s", entrypath, self.artifacts_dir)
        if not self.osutils.file_exists(entrypath):
            raise ActionFailedError("main entry point %s does not exist" % entrypath)

        args = [entrypoint, "--bundle", "--platform=node", "--format=cjs"]
        skip_minify = "minify" in self.bundler_config and not self.bundler_config["minify"]
        skip_sourcemap = "sourcemap" in self.bundler_config and not self.bundler_config["sourcemap"]
        if not skip_minify:
            args.append("--minify")
        if not skip_sourcemap:
            args.append("--sourcemap")
        if "target" not in self.bundler_config:
            args.append("--target=es2020")
        else:
            args.append("--target=" + self.bundler_config["target"])
        args.append("--outdir=" + self.artifacts_dir)
        try:
            self.subprocess_esbuild.run(args, cwd=self.source_dir)
        except EsbuildExecutionError as ex:
            raise ActionFailedError(str(ex))
