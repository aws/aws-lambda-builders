"""
Wrapper around calling npm through a subprocess.
"""

import logging
import json

LOG = logging.getLogger(__name__)


class NpmExecutionError(Exception):

    """
    Exception raised in case NPM execution fails.
    It will pass on the standard error output from the NPM console.
    """

    MESSAGE = "NPM Failed: {message}"

    def __init__(self, **kwargs):
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


class SubprocessNpm(object):

    """
    Wrapper around the NPM command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, osutils, npm_exe=None):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type npm_exe: str
        :param npm_exe: Path to the NPM binary. If not set,
            the default executable path npm will be used
        """
        self.osutils = osutils

        if npm_exe is None:
            if osutils.is_windows():
                npm_exe = 'npm.cmd'
            else:
                npm_exe = 'npm'

        self.npm_exe = npm_exe

    def run(self, args, cwd=None):

        """
        Runs the action.

        :type args: list
        :param args: Command line arguments to pass to NPM

        :type cwd: str
        :param cwd: Directory where to execute the command (defaults to current dir)

        :rtype: str
        :return: text of the standard output from the command

        :raises aws_lambda_builders.workflows.nodejs_npm.npm.NpmExecutionError:
            when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.

        :raises ValueError: if arguments are not provided, or not a list
        """

        if not isinstance(args, list):
            raise ValueError('args must be a list')

        if not args:
            raise ValueError('requires at least one arg')

        invoke_npm = [self.npm_exe] + args

        LOG.debug("executing NPM: %s", invoke_npm)

        p = self.osutils.popen(invoke_npm,
                               stdout=self.osutils.pipe,
                               stderr=self.osutils.pipe,
                               cwd=cwd)

        out, err = p.communicate()

        if p.returncode != 0:
            raise NpmExecutionError(message=err.decode('utf8').strip())

        return out.decode('utf8').strip()


class NpmModulesUtils(object):

    """
    Utility class that abstracts operations on NPM packages
    and manifest files
    """

    def __init__(self, osutils, subprocess_npm, scratch_dir):
        """
        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of NPM Subprocess for executing the NPM binary

        :type scratch_dir: str
        :param scratch_dir: a writable temporary directory
        """

        self.osutils = osutils
        self.subprocess_npm = subprocess_npm
        self.scratch_dir = scratch_dir

    def clean_copy(self, package_dir, delete_package_lock=False):

        """
        Produces a clean copy of a NPM package source from a project directory,
        so it can be packaged without temporary files, development or test resources
        or dependencies.

        :type package_dir: str
        :param package_dir: Path to a NPM project directory

        :type delete_package_lock: bool
        :param delete_package_lock: If true, package-lock.json will be removed in the copy
        """

        target_dir = self.osutils.tempdir(self.scratch_dir)

        package_path = 'file:{}'.format(self.osutils.abspath(package_dir))

        LOG.debug('NODEJS packaging %s to %s', package_path, self.scratch_dir)

        tarfile_name = self.subprocess_npm.run(['pack', '-q', package_path], cwd=self.scratch_dir)

        LOG.debug('NODEJS packed to %s', tarfile_name)

        tarfile_path = self.osutils.joinpath(self.scratch_dir, tarfile_name)

        LOG.debug('NODEJS extracting to %s', target_dir)

        self.osutils.extract_tarfile(tarfile_path, target_dir)

        package_lock = self.osutils.joinpath(target_dir, 'package', 'package-lock.json')
        if delete_package_lock and self.osutils.file_exists(package_lock):
            self.osutils.remove_file(package_lock)

        return self.osutils.joinpath(target_dir, 'package')

    def is_local_dependency(self, module_path):
        """
        Calculates if the module path from a dependency reference is
        local or remote

        :type module_path: str
        :param module_path: Dependency reference value (from package.json)

        """

        return module_path.startswith('file:') or \
            module_path.startswith('.') or \
            module_path.startswith('/') or \
            module_path.startswith('~/')

    def get_local_dependencies(self, package_dir, dependency_key='dependencies'):
        """
        Returns a dictionary with only local dependencies from a package.json manifest

        :type package_dir: str
        :param package_dir: path to a NPM project directory (containing package.json)

        :type dependency_key: str
        :param dependency_key: dependency type to return, corresponds to a key of package.json.
            (for example, 'dependencies' or 'optionalDependencies')
        """

        package_json = json.loads(self.osutils.get_text_contents(self.osutils.joinpath(package_dir, 'package.json')))
        if dependency_key not in package_json.keys():
            return {}

        dependencies = package_json[dependency_key]

        return dict(
            [(name, module_path) for (name, module_path) in dependencies.items()
                if self.is_local_dependency(module_path)]
        )

    def has_local_dependencies(self, package_dir):
        """
        Checks if a NPM project has local dependencies

        :type package_dir: str
        :param package_dir: path to a NPM project directory (containing package.json)
        """
        return len(self.get_local_dependencies(package_dir, 'dependencies')) > 0 or \
            len(self.get_local_dependencies(package_dir, 'optionalDependencies')) > 0

    def pack_to_tar(self, package_dir):
        """
        Runs npm pack to produce a tar containing project sources, which can be used
        as a target for project dependencies

        :type package_dir: str
        :param package_dir: path to a NPM project directory (containing package.json)
        """
        package_path = "file:{}".format(self.osutils.abspath(package_dir))

        tarfile_name = self.subprocess_npm.run(['pack', '-q', package_path], cwd=self.scratch_dir)

        return self.osutils.joinpath(self.scratch_dir, tarfile_name)

    def update_dependency(self, package_dir, name, module_path, dependency_key='dependencies'):
        """
        Updates package.json by rewriting a dependency to point to a specified module path

        :type package_dir: str
        :param package_dir: path to a NPM project directory (containing package.json)

        :type name: str
        :param name: the name of the dependency (sub-key in package.json)

        :type module_path: str
        :param module_path: new destination for the dependency

        :type dependency_key: str
        :param dependency_key: dependency type to return, corresponds to a key of package.json.
            (for example, 'dependencies' or 'optionalDependencies')
        """

        package_json_path = self.osutils.joinpath(package_dir, 'package.json')
        package_json = json.loads(self.osutils.get_text_contents(package_json_path))

        package_json[dependency_key][name] = module_path

        self.osutils.write_text_contents(package_json_path, json.dumps(package_json))
