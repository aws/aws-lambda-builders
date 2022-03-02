"""
Commonly used utilities
"""

import os
import platform
import tarfile
import subprocess
import shutil
import json

from aws_lambda_builders.workflows.nodejs_npm.actions import NodejsNpmCIAction, NodejsNpmInstallAction


class OSUtils(object):

    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def copy_file(self, file_path, destination_path):
        return shutil.copy2(file_path, destination_path)

    def extract_tarfile(self, tarfile_path, unpack_dir):
        with tarfile.open(tarfile_path, "r:*") as tar:
            tar.extractall(unpack_dir)

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def joinpath(self, *args):
        return os.path.join(*args)

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

    def parse_json(self, path):
        with open(path) as json_file:
            return json.load(json_file)


def get_install_action(source_dir, artifacts_dir, subprocess_npm, osutils, build_options):
    """
    Get the install action used to install dependencies at artifacts_dir

    :type source_dir: str
    :param source_dir: an existing (readable) directory containing source files

    :type artifacts_dir: str
    :param artifacts_dir: Dependencies will be installed in this directory.

    :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
    :param osutils: An instance of OS Utilities for file manipulation

    :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
    :param subprocess_npm: An instance of the NPM process wrapper

    :type build_options: Dict
    :param build_options: Object containing build options configurations

    :type is_production: bool
    :param is_production: NPM installation mode is production (eg --production=false to force dev dependencies)

    :rtype: BaseAction
    :return: Install action to use
    """
    lockfile_path = osutils.joinpath(source_dir, "package-lock.json")
    shrinkwrap_path = osutils.joinpath(source_dir, "npm-shrinkwrap.json")

    npm_ci_option = False
    if build_options and isinstance(build_options, dict):
        npm_ci_option = build_options.get("use_npm_ci", False)

    if (osutils.file_exists(lockfile_path) or osutils.file_exists(shrinkwrap_path)) and npm_ci_option:
        return NodejsNpmCIAction(artifacts_dir, subprocess_npm=subprocess_npm)

    return NodejsNpmInstallAction(artifacts_dir, subprocess_npm=subprocess_npm, is_production=False)
