"""
Action to resolve NodeJS dependencies using NPM
"""

import json
import logging
from os import sep as path_sep

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .npm import NpmExecutionError

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


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

            LOG.debug("NODEJS searching for local dependencies")

            local_manifest_path = self.osutils.joinpath(self.artifacts_dir, 'package', 'package.json')
            local_dependencies = get_local_dependencies(self.manifest_path)
            for (dep_name, dep_path) in local_dependencies.items():
                dep_scratch_dir = self.osutils.joinpath(self.scratch_dir, str(abs(hash(dep_name))))
                dep_artifacts_dir = self.osutils.joinpath(dep_scratch_dir, 'unpacked')
                dependency_tarfile_path = package_local_dependency(package_path[5:], dep_path, dep_artifacts_dir, dep_scratch_dir, self.osutils, self.subprocess_npm)
                local_packaged_dep_path = self.osutils.joinpath(self.artifacts_dir, 'package', 'local_dep')
                if not self.osutils.dir_exists(local_packaged_dep_path):
                    self.osutils.mkdir(local_packaged_dep_path)
                dependency_tarfile_path = self.osutils.copy_file(dependency_tarfile_path, self.osutils.joinpath(local_packaged_dep_path))
                update_manifest(local_manifest_path, dep_name, dependency_tarfile_path, self.osutils)

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

        :raises lambda_builders.actions.ActionFailedError: when .npmrc copying fails
        """

        try:
            npmrc_path = self.osutils.joinpath(self.artifacts_dir, ".npmrc")
            if self.osutils.file_exists(npmrc_path):
                LOG.debug(".npmrc cleanup in: %s", self.artifacts_dir)
                self.osutils.remove_file(npmrc_path)

        except OSError as ex:
            raise ActionFailedError(str(ex))


def get_local_dependencies(manifest_path):
    """
    Helper function to extract all local dependencies in a package.json manifest
    """

    with open(manifest_path) as manifest_file:
        manifest = json.loads(manifest_file.read())

        if 'dependencies' in manifest:
            return dict((k, v) for (k, v) in manifest['dependencies'].items() if is_local_dependency(v))
        else:
            return {}


def is_local_dependency(path):
    """
    Helper function to check if package dependency is a local package
    """

    try:
        return path.startswith('file:') or path.startswith('.')
    except AttributeError:
        return False


def package_local_dependency(parent_package_path, rel_package_path, artifact_dir, scratch_dir, osutils, subprocess_npm):
    if rel_package_path.startswith('file:'):
        rel_package_path = rel_package_path[5:].strip()

    if rel_package_path.startswith('.'):
        package_path = osutils.abspath(osutils.joinpath(parent_package_path, rel_package_path))

    LOG.debug("NODEJS packaging dependency %s to %s", package_path, scratch_dir)

    if not osutils.dir_exists(scratch_dir):
        osutils.mkdir(scratch_dir)

    tarfile_name = subprocess_npm.run(["pack", "-q", package_path], cwd=scratch_dir).splitlines()[-1]

    LOG.debug("NODEJS packed dependency to %s", tarfile_name)

    tarfile_path = osutils.joinpath(scratch_dir, tarfile_name)

    LOG.debug("NODEJS extracting to %s", artifact_dir)

    osutils.extract_tarfile(tarfile_path, artifact_dir)

    LOG.debug("NODEJS searching for subpackage local dependencies")

    # manifest_path = osutils.joinpath(package_path, 'package.json')
    # local_dependencies = get_local_dependencies(manifest_path)
    # for (dep_name, dep_path) in local_dependencies.items():
    #     dep_scratch_dir = osutils.joinpath(scratch_dir, '..', hash(dep_name))
    #     dep_artifacts_dir = osutils.joinpath(dep_scratch_dir, 'unpacked')
    #     dependency_tarfile_path = package_local_dependency(package_path[5:], dep_path, dep_artifacts_dir, dep_scratch_dir, self.osutils, self.subprocess_npm)
    #     update_manifest(manifest_path, dep_name, dependency_tarfile_path)

    localized_package_dir = osutils.joinpath(artifact_dir, 'package')

    LOG.debug("NODEJS repackaging dependency %s to %s", artifact_dir, localized_package_dir)

    tarfile_name = subprocess_npm.run(["pack", "-q", localized_package_dir], cwd=localized_package_dir).splitlines()[-1]

    return osutils.joinpath(localized_package_dir, tarfile_name)


def update_manifest(manifest_path, dep_name, dependency_tarfile_path, osutils):
    """
    Helper function to update dependency path to localized tar
    """

    package_path = osutils.dirname(manifest_path)
    manifest_backup = osutils.copy_file(manifest_path, f'{manifest_path}.bak')

    with open(manifest_backup, 'r') as manifest_backup_file:
        manifest = json.loads(manifest_backup_file.read())

        if 'dependencies' in manifest and dep_name in manifest['dependencies']:
            dep_rel_path = osutils.relative_path(dependency_tarfile_path, start=package_path)
            dep_rel_path = osutils.joinpath('.', dep_rel_path).replace(path_sep, "/")
            manifest['dependencies'][dep_name] = f'file:{dep_rel_path}'

            with open(manifest_path, 'w') as manifest_write_file:
                manifest_write_file.write(json.dumps(manifest, indent=4))
