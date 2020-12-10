"""
Commonly used utilities
"""

import json
import logging
import os
import platform
import tarfile
import subprocess
import shutil

LOG = logging.getLogger(__name__)


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def copy_file(self, file_path, destination_path):
        return shutil.copy2(file_path, destination_path)

    def dir_exists(self, directory):
        return os.path.isdir(directory)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:
            tar.extractall(unpack_dir)

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def filename(self, filename):
        return os.path.basename(filename)

    def joinpath(self, *args):
        return os.path.join(*args)

    def mkdir(self, path):
        return os.mkdir(path)

    def open_file(self, filename, mode="r"):
        return open(filename, mode)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    @property
    def pipe(self):
        return subprocess.PIPE

    def dirname(self, path):
        return os.path.dirname(path)

    def remove_file(self, filename):
        return os.remove(filename)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return platform.system().lower() == "windows"


class DependencyUtils(object):

    """
    Collection of helper functions for managing local NPM dependencies
    """

    @staticmethod
    def get_local_dependencies(manifest_path, osutils):
        """
        Helper function to extract all local dependencies in a package.json manifest
        """

        with osutils.open_file(manifest_path) as manifest_file:
            manifest = json.loads(manifest_file.read())

            if "dependencies" in manifest:
                return dict(
                    (k, v) for (k, v) in manifest["dependencies"].items() if DependencyUtils.is_local_dependency(v)
                )
            else:
                return {}

    @staticmethod
    def is_local_dependency(path):
        """
        Helper function to check if package dependency is a local package
        """

        try:
            return path.startswith("file:") or path.startswith(".")
        except AttributeError:
            return False

    @staticmethod
    def package_local_dependency(
        parent_package_path, rel_package_path, artifacts_dir, scratch_dir, output_dir, osutils, subprocess_npm
    ):
        """
        Helper function to recurse local dependencies and package them to a common directory
        """

        if rel_package_path.startswith("file:"):
            rel_package_path = rel_package_path[5:].strip()

        package_path = osutils.abspath(osutils.joinpath(parent_package_path, rel_package_path))

        if not osutils.dir_exists(scratch_dir):
            osutils.mkdir(scratch_dir)

        if output_dir is None:
            # TODO: get a higher level output_dir to keep process locals between jobs
            output_dir = osutils.joinpath(artifacts_dir, "@aws_lambda_builders_local_dep")
            if not osutils.dir_exists(output_dir):
                osutils.mkdir(output_dir)
            top_level = True
        else:
            tarfile_name = subprocess_npm.run(["pack", "-q", package_path], cwd=scratch_dir).splitlines()[-1]
            tarfile_path = osutils.joinpath(scratch_dir, tarfile_name)

            LOG.debug("NODEJS extracting child dependency for recursive dependency check")

            osutils.extract_tarfile(tarfile_path, artifacts_dir)

            top_level = False

        local_manifest_path = osutils.joinpath(artifacts_dir, "package", "package.json")
        local_dependencies = DependencyUtils.get_local_dependencies(local_manifest_path, osutils)
        for (dep_name, dep_path) in local_dependencies.items():
            dep_scratch_dir = osutils.joinpath(scratch_dir, str(abs(hash(dep_name))))

            # TODO: if dep_scratch_dir exists (anywhere up path), it means we've already processed it this round, skip

            dep_artifacts_dir = osutils.joinpath(dep_scratch_dir, "unpacked")

            LOG.debug("NODEJS packaging dependency, %s, from %s to %s", dep_name, parent_package_path, output_dir)

            dependency_tarfile_path = DependencyUtils.package_local_dependency(
                package_path, dep_path, dep_artifacts_dir, dep_scratch_dir, output_dir, osutils, subprocess_npm
            )

            packaged_dependency_tarfile_path = osutils.joinpath(output_dir, osutils.filename(dependency_tarfile_path))
            osutils.copy_file(dependency_tarfile_path, output_dir)

            LOG.debug("NODEJS packed localized child dependency to %s", packaged_dependency_tarfile_path)

            LOG.debug("NODEJS updating package.json %s", local_manifest_path)

            DependencyUtils.update_manifest(local_manifest_path, dep_name, packaged_dependency_tarfile_path, osutils)

        if not top_level:
            localized_package_dir = osutils.joinpath(artifacts_dir, "package")

            LOG.debug("NODEJS repackaging child dependency")

            tarfile_name = subprocess_npm.run(
                ["pack", "-q", localized_package_dir], cwd=localized_package_dir
            ).splitlines()[-1]

            return osutils.joinpath(localized_package_dir, tarfile_name)

    @staticmethod
    def update_manifest(manifest_path, dep_name, dependency_tarfile_path, osutils):
        """
        Helper function to update dependency path to localized tar
        """

        manifest_backup = "{}.bak".format(manifest_path)
        osutils.copy_file(manifest_path, manifest_backup)

        with osutils.open_file(manifest_backup, "r") as manifest_backup_file:
            manifest = json.loads(manifest_backup_file.read())

            if "dependencies" in manifest and dep_name in manifest["dependencies"]:
                manifest["dependencies"][dep_name] = "file:{}".format(dependency_tarfile_path)

                with osutils.open_file(manifest_path, "w") as manifest_write_file:
                    manifest_write_file.write(json.dumps(manifest, indent=4))

        osutils.remove_file(manifest_backup)
