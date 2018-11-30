"""
Installs packages using NPM
"""

import logging

from aws_lambda_builders.workflows.python_pip.utils import OSUtils

LOG = logging.getLogger(__name__)


class PackagerError(Exception):
    pass


class RequirementsFileNotFoundError(PackagerError):
    def __init__(self, requirements_path):
        super(RequirementsFileNotFoundError, self).__init__(
            'Requirements file not found: %s' % requirements_path)


class NpmNotFoundError(PackagerError):
    def __init__(self, npm_path):
        super(NpmNotFoundError, self).__init__(
            'NPM executable not found: %s' % npm_path)


class SubprocessNpm(object):
    """Wrapper around calling npm through a subprocess."""
    def __init__(self, osutils=None, npm_exe=None):
        if osutils is None:
            osutils = OSUtils()
        self._osutils = osutils

        if npm_exe is None:
            npm_exe = osutils.find_executable('npm')

        if not osutils.file_exists(npm_exe):
            raise NpmNotFoundError(npm_exe)

        self.npm_exe = npm_exe

    def main(self, args, cwd=None, env_vars=None):
        if env_vars is None:
            env_vars = self._osutils.environ()

        invoke_npm = [self.npm_exe] + args

        LOG.debug("executing NPM: %s", invoke_npm)

        p = self._osutils.popen(invoke_npm,
                                stdout=self._osutils.pipe,
                                stderr=self._osutils.pipe,
                                env=env_vars,
                                cwd=cwd)
        out, err = p.communicate()
        rc = p.returncode
        return rc, out, err


class NodejsNpmDependencyBuilder(object):
    def __init__(self, runtime, osutils=None, dependency_builder=None):
        """Initialize a NodejsNpmDependencyBuilder.

        :type runtime: str
        :param runtime: Python version to build dependencies for. This can
            either be python2.7, python3.6 or python3.7. These are currently the
            only supported values.

        :type osutils: :class:`lambda_builders.utils.OSUtils`
        :param osutils: A class used for all interactions with the
            outside OS.

        :type dependency_builder: :class:`DependencyBuilder`
        :param dependency_builder: This class will be used to build the
            dependencies of the project.
        """
        self.osutils = osutils
        if osutils is None:
            self.osutils = OSUtils()

        # if dependency_builder is None:
        #    dependency_builder = DependencyBuilder(self.osutils, runtime)
        # self._dependency_builder = dependency_builder

    def build_dependencies(self, project_dir, scratch_dir, manifest_path, ui=None, config=None):
        """Builds a NodeJS project's dependencies into an artifact directory.

        :type project_dir: str
        :param project_dir: Directory where to store artefacts

        :type scratch_dir_path: str
        :param scratch_dir_path: Directory to write temp files into.

        :type manifest_path: str
        :param manifest_path: Location of the project package.json

        :type ui: :class:`lambda_builders.utils.UI` or None
        :param ui: A class that traps all progress information such as status
            and errors. If injected by the caller, it can be used to monitor
            the status of the build process or forward this information
            elsewhere.

        :type config: :class:`lambda_builders.utils.Config` or None
        :param config: To be determined. This is an optional config object
            we can extend at a later date to add more options to how pip is
            called.
        """

        LOG.debug("NODEJS building in: %s from: %s", project_dir, manifest_path)

        if not self.osutils.file_exists(manifest_path):
            raise RequirementsFileNotFoundError(manifest_path)

        subprocess = SubprocessNpm(self.osutils)

        subprocess.main(['install', '--production'], cwd=project_dir)
