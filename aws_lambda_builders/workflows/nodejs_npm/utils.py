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

    def joinpath(self, *args):
        return os.path.join(*args)

    def mkdir(self, path):
        return os.mkdir(path)

    def makedirs(self, path):
        return os.makedirs(path)

    def normpath(self, *args):
        return os.path.normpath(*args)

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

    def walk(self, dir, topdown=True):
        return os.walk(dir, topdown)


class DependencyUtils(object):
    """
    Collection of helper functions for managing local NPM dependencies
    """

    @staticmethod
    def ship_module(package_path, from_dir, to_dir, osutils, subprocess_npm):
        """
        Helper function to package a module and extract it to a new directory

        Parameters
        ----------
        package_path : str
            Package path
        from_dir : str
            Origin directory path
        to_dir : str
            Destination directory path
        osutils : OSUtils
            OS utils
        subprocess_npm : SubprocessNpm
            NPM process
        """
        tarfile_name = subprocess_npm.run(["pack", "-q", package_path], cwd=from_dir).splitlines()[-1]

        LOG.debug("NODEJS packed to %s", tarfile_name)

        tarfile_path = osutils.joinpath(from_dir, tarfile_name)

        LOG.debug("NODEJS extracting to %s", to_dir)

        osutils.extract_tarfile(tarfile_path, to_dir)

    @staticmethod
    def get_local_dependencies(manifest_path, osutils):
        """
        Helper function to extract all local dependencies in a package.json manifest

        Parameters
        ----------
        manifest_path : str
            Manifest path
        osutils : OSUtils
            OS utils

        Returns
        -------
        dict
            Dict of local dependencies key->value if any, empty otherwise
        """
        with osutils.open_file(manifest_path) as manifest_file:
            manifest = json.loads(manifest_file.read())

            if "dependencies" in manifest:
                return dict(
                    (k, v) for (k, v) in manifest["dependencies"].items() if DependencyUtils.is_local_dependency(v)
                )

            return {}

    @staticmethod
    def is_local_dependency(path):
        """
        Helper function to check if a dependency is a local package

        Parameters
        ----------
        path : str
            Path to check

        Returns
        -------
        boolean
            True if a local dependency, False otherwise
        """
        try:
            return path.startswith("file:") or path.startswith(".")
        except AttributeError:
            return False

    @staticmethod
    def package_dependencies(manifest_path, scratch_dir, packed_manifests, osutils, subprocess_npm):
        """
        Recursively packages NPM dependencies, including local ones.
        Handles circular dependencies and skips already processed ones.

        Parameters
        ----------
        manifest_path : str
            Path to the manifest to package
        scratch_dir : str
            Path to the scratch directory
        packed_manifests : dict
            Dict of hashes pointing to packed manifest tar used to avoid
        osutils : OSUtils
            OS utils
        subprocess_npm : SubprocessNpm
            NPM process

        Returns
        -------
        string
            Path to the packed tar file
        """
        manifest_path = osutils.normpath(manifest_path)
        LOG.debug("NODEJS processing %s", manifest_path)
        manifest_hash = str(abs(hash(manifest_path)))
        if manifest_hash in packed_manifests:
            # Already processed or circular dependency
            # If empty, it will be removed from the manifest
            return packed_manifests[manifest_hash]
        packed_manifests[manifest_hash] = ""
        manifest_dir = osutils.dirname(manifest_path)
        manifest_scratch_dir = osutils.joinpath(scratch_dir, manifest_hash)
        manifest_scratch_package_dir = osutils.joinpath(manifest_scratch_dir, "package")
        osutils.makedirs(manifest_scratch_package_dir)

        # Pack and copy module to scratch so that we don't update the customers files in place
        DependencyUtils.ship_module(manifest_dir, scratch_dir, manifest_scratch_dir, osutils, subprocess_npm)

        # Process local children dependencies
        local_dependencies = DependencyUtils.get_local_dependencies(manifest_path, osutils)

        for (dep_name, dep_path) in local_dependencies.items():
            if dep_path.startswith("file:"):
                dep_path = dep_path[5:].strip()
            dep_manifest = osutils.joinpath(manifest_dir, dep_path, "package.json")

            tar_path = DependencyUtils.package_dependencies(
                dep_manifest, scratch_dir, packed_manifests, osutils, subprocess_npm
            )

            manifest_scratch_path = osutils.joinpath(manifest_scratch_package_dir, "package.json")

            # Make a backup we will use to restore in the final build folder
            osutils.copy_file(manifest_scratch_path, manifest_scratch_path + ".bak")

            DependencyUtils.update_manifest(manifest_scratch_path, dep_name, tar_path, osutils)

        # Pack the current dependency
        tarfile_name = subprocess_npm.run(["pack", "-q", manifest_scratch_package_dir], cwd=scratch_dir).splitlines()[
            -1
        ]

        packed_manifests[manifest_hash] = osutils.joinpath(scratch_dir, tarfile_name)

        LOG.debug("NODEJS %s packed to %s", manifest_scratch_package_dir, packed_manifests[manifest_hash])

        return packed_manifests[manifest_hash]

    @staticmethod
    def update_manifest(manifest_path, dep_name, dependency_tarfile_path, osutils):
        """
        Helper function to update dependency path to localized tar

        Parameters
        ----------
        manifest_path : str
            Manifest path to update
        dep_name : str
            Dependency name
        dependency_tarfile_path : str
            Packed dependency tar file path
        osutils : OSUtils
            OS utils
        """
        with osutils.open_file(manifest_path, "r") as manifest_read_file:
            manifest = json.loads(manifest_read_file.read())

        if "dependencies" in manifest and dep_name in manifest["dependencies"]:
            if not dependency_tarfile_path:
                LOG.debug("NODEJS removing dep '%s' from '%s'", dep_name, manifest_path)
                manifest["dependencies"].pop(dep_name)
            else:
                LOG.debug(
                    "NODEJS updating dep '%s' of '%s' with '%s'", dep_name, manifest_path, dependency_tarfile_path
                )
                manifest["dependencies"][dep_name] = "file:{}".format(dependency_tarfile_path)

            with osutils.open_file(manifest_path, "w") as manifest_write_file:
                manifest_write_file.write(json.dumps(manifest, indent=4))
