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

    """

    def __init__(self, osutils, subprocess_npm, scratch_dir):
        self.osutils = osutils
        self.subprocess_npm = subprocess_npm
        self.scratch_dir = scratch_dir

    def clean_copy(self, package_dir):
        target_dir = self.osutils.tempdir(self.scratch_dir)

        package_path = 'file:{}'.format(self.osutils.abspath(package_dir))

        LOG.debug('NODEJS packaging %s to %s', package_path, self.scratch_dir)

        tarfile_name = self.subprocess_npm.run(['pack', '-q', package_path], cwd=self.scratch_dir)

        LOG.debug('NODEJS packed to %s', tarfile_name)

        tarfile_path = self.osutils.joinpath(self.scratch_dir, tarfile_name)

        LOG.debug('NODEJS extracting to %s', target_dir)

        self.osutils.extract_tarfile(tarfile_path, target_dir)
        return self.osutils.joinpath(target_dir, 'package')

    def is_local_dependency(self, module_path):
        return module_path.startswith('file:') or module_path.startswith('.') or module_path.startswith('/')

    def get_local_dependencies(self, package_dir, dependency_key='dependencies'):
        package_json = json.loads(self.osutils.get_text_contents(self.osutils.joinpath(package_dir, 'package.json')))
        if not dependency_key in package_json.keys():
            return {}

        dependencies = package_json[dependency_key]

        return dict([(name, module_path) for (name, module_path) in dependencies.items() if self.is_local_dependency(module_path)])

    def has_local_dependencies(self, package_dir):
        return len(self.get_local_dependencies(package_dir, 'dependencies')) > 0 or \
            len(self.get_local_dependencies(package_dir, 'optionalDependencies')) > 0

    def pack_to_tar(self, module_dir):
        package_path = "file:{}".format(self.osutils.abspath(module_dir))

        tarfile_name = self.subprocess_npm.run(['pack', '-q', package_path], cwd=self.scratch_dir)

        return self.osutils.joinpath(self.scratch_dir, tarfile_name)

    def update_dependency(self, package_dir, name, module_path, dependency_key):
        package_json_path = self.osutils.joinpath(package_dir, 'package.json')
        package_json = json.loads(self.osutils.get_text_contents(package_json_path))

        package_json[dependency_key][name] = module_path

        self.osutils.write_text_contents(package_json_path, json.dumps(package_json))

    def rewrite_local_dependencies(self, work_dir, original_package_dir):
        for dependency_key in ['dependencies', 'optionalDependencies']:
            for (name, module_path) in self.get_local_dependencies(work_dir, dependency_key).items():
                if module_path.startswith('file:'):
                    module_path = module_path[5:]

                physical_dir = self.osutils.joinpath(original_package_dir, module_path)
                if self.has_local_dependencies(physical_dir):
                    module_path = self.clean_copy(physical_dir)
                    self.rewrite_local_dependencies(module_path, physical_dir)
                    physical_dir = module_path

                new_module_path = 'file:{}'.format(self.pack_to_tar(physical_dir))
                self.update_dependency(work_dir, name, new_module_path, dependency_key)
