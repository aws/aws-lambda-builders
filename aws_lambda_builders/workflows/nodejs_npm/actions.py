"""
Action to resolve NodeJS dependencies using NPM
"""

import logging
import os
import re
from typing import Optional

from aws_lambda_builders import utils
from aws_lambda_builders.actions import ActionFailedError, BaseAction, Purpose
from aws_lambda_builders.utils import extract_tarfile
from aws_lambda_builders.workflows.nodejs_npm.lockfile_closure import production_closure
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError, SubprocessNpm

LOG = logging.getLogger(__name__)

# `pkg` or `@scope/pkg` and nothing else, so no traversal, absolute path or drive letter gets through.
NODE_MODULES_PACKAGE_NAME = re.compile(r"^(?:@[^/\\:]+/)?[^.@/\\:][^/\\:]*$")


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

            extract_tarfile(tarfile_path, self.artifacts_dir)

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmInstallOrUpdateBaseAction(BaseAction):
    """
    A base Lambda Builder Action that is used for installs or updating NPM project dependencies
    """

    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, install_dir: str, subprocess_npm: SubprocessNpm):
        """
        Parameters
        ----------
        install_dir : str
            Dependencies will be installed in this directory.
        subprocess_npm : SubprocessNpm
            An instance of the NPM process wrapper
        """

        super().__init__()
        self.install_dir = install_dir
        self.subprocess_npm = subprocess_npm


class NodejsNpmInstallAction(NodejsNpmInstallOrUpdateBaseAction):
    """
    A Lambda Builder Action that installs NPM project dependencies
    """

    NAME = "NpmInstall"
    DESCRIPTION = "Installing dependencies from NPM"

    def __init__(self, install_dir: str, subprocess_npm: SubprocessNpm, install_links: Optional[bool] = False):
        """
        Parameters
        ----------
        install_dir : str
            Dependencies will be installed in this directory.
        subprocess_npm : SubprocessNpm
            An instance of the NPM process wrapper
        install_links : Optional[bool]
            Uses the --install-links npm option if True, by default False. Required when installing into the
            source directory, so that local file dependencies are installed as regular dependencies.
        """

        super().__init__(install_dir=install_dir, subprocess_npm=subprocess_npm)
        self.install_links = install_links

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """
        try:
            LOG.debug("NODEJS installing production dependencies in: %s", self.install_dir)

            command = ["install", "-q", "--no-audit", "--no-save", "--omit=dev"]
            if self.install_links:
                command.append("--install-links")
            self.subprocess_npm.run(command, cwd=self.install_dir)

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmUpdateAction(NodejsNpmInstallOrUpdateBaseAction):
    """
    A Lambda Builder Action that installs NPM project dependencies, ignoring any lockfile.

    Used when building in source and either no lockfile applies or `experimentalNodejsMonorepo` is off -
    which, the flag being opt-in, is still every in-source build by default, lockfile or not.
    `--no-package-lock` means dependency versions are resolved afresh on every build, so once a caller
    opts in, a project that does have a lockfile is installed with NodejsNpmInstallAction instead to keep
    builds reproducible.
    """

    NAME = "NpmUpdate"
    DESCRIPTION = "Updating dependencies from NPM"

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """
        try:
            LOG.debug("NODEJS updating production dependencies in: %s", self.install_dir)

            command = [
                "update",
                "--no-audit",
                "--no-save",
                "--omit=dev",
                "--no-package-lock",
                "--install-links",
            ]
            self.subprocess_npm.run(command, cwd=self.install_dir)

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

    def __init__(self, install_dir: str, subprocess_npm: SubprocessNpm, install_links: Optional[bool] = False):
        """
        Parameters
        ----------
        install_dir : str
            Dependencies will be installed in this directory.
        subprocess_npm : SubprocessNpm
            An instance of the NPM process wrapper
        install_links : Optional[bool]
            Uses the --install-links npm option if True, by default False
        """

        super(NodejsNpmCIAction, self).__init__()
        self.install_dir = install_dir
        self.subprocess_npm = subprocess_npm
        self.install_links = install_links

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """

        try:
            LOG.debug("NODEJS installing ci in: %s", self.install_dir)

            command = ["ci"]
            if self.install_links:
                command.append("--install-links")

            self.subprocess_npm.run(command, cwd=self.install_dir)

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmrcAndLockfileCopyAction(BaseAction):
    """
    A Lambda Builder Action that copies lockfile and NPM config file .npmrc
    """

    NAME = "CopyNpmrcAndLockfile"
    DESCRIPTION = "Copying configuration from .npmrc and dependencies from lockfile/shrinkwrap"
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

        super(NodejsNpmrcAndLockfileCopyAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.source_dir = source_dir
        self.osutils = osutils

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when copying fails
        """

        try:
            for filename in [".npmrc", "package-lock.json", "npm-shrinkwrap.json"]:
                file_path = self.osutils.joinpath(self.source_dir, filename)
                if self.osutils.file_exists(file_path):
                    LOG.debug("%s copying in: %s", filename, self.artifacts_dir)
                    self.osutils.copy_file(file_path, self.artifacts_dir)

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


class NodejsNpmTestAction(NodejsNpmInstallOrUpdateBaseAction):
    """
    A Lambda Builder Action that runs tests in NPM project
    """

    NAME = "NpmTest"
    DESCRIPTION = "Running tests from NPM"

    def execute(self):
        """
        Runs the action if environment variable `SAM_NPM_RUN_TEST_WITH_BUILD` is `true`.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """
        try:
            is_run_test_with_build = os.getenv("SAM_NPM_RUN_TEST_WITH_BUILD", "False")
            if is_run_test_with_build == "true":
                LOG.debug("NODEJS running tests in: %s", self.install_dir)

                command = ["test", "--if-present"]
                self.subprocess_npm.run(command, cwd=self.install_dir)
            else:
                LOG.debug("NODEJS skipping tests")
                LOG.debug("Add env variable 'SAM_NPM_RUN_TEST_WITH_BUILD=true' to run tests with build")

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmLinkDependencyClosureAction(BaseAction):
    """
    A Lambda Builder Action that links only this function's own dependencies into the artifacts directory.

    Used when npm installed somewhere other than the function's directory, which is what npm does for a
    workspaces monorepo: it hoists every workspace package's dependencies into one node_modules at the
    monorepo root. Linking that whole directory would ship every sibling function's dependencies too, so
    this asks npm which packages this function actually resolves and links those under their own names.

    Names come from the install path rather than the manifest (`_link_name`), and when npm reports no
    closure the installed packages are linked one by one (`_link_every_installed_package`).
    """

    NAME = "NpmLinkDependencyClosure"
    DESCRIPTION = "Linking this function's dependencies into the artifacts directory"
    PURPOSE = Purpose.LINK_SOURCE

    def __init__(self, install_dir, project_root, artifacts_dir, subprocess_npm, osutils):
        """
        Parameters
        ----------
        install_dir : str
            the directory npm ran in, whose project's closure is wanted
        project_root : str
            the directory npm installed into, linked whole if the closure cannot be resolved
        artifacts_dir : str
            an existing (writable) directory where node_modules is assembled
        subprocess_npm : aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
            An instance of the NPM process wrapper
        osutils : aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
            An instance of OS Utilities for file manipulation
        """
        super(NodejsNpmLinkDependencyClosureAction, self).__init__()
        self._install_dir = install_dir
        self._project_root = project_root
        self._artifacts_dir = artifacts_dir
        self._subprocess_npm = subprocess_npm
        self._osutils = osutils

    def execute(self):
        # npm's hidden lockfile records the tree the install just reified, so read that rather than
        # paying an npm process per function; it answers None whenever it cannot be trusted
        closure = production_closure(self._project_root, self._install_dir)
        if closure is None:
            closure = self._subprocess_npm.resolve_dependency_closure(self._install_dir)
        destination = os.path.join(self._artifacts_dir, "node_modules")

        if closure is None:
            self._link_every_installed_package(destination)
            return

        for name, package_dir in self._packages_by_name(self._outermost_packages(closure)).items():
            self._link(package_dir, destination, name)

    def _link_every_installed_package(self, destination):
        """
        Link every package npm installed, when npm could not say which ones this function resolves.

        Per-entry links, not one link for the whole tree: only the overlay is a superset of what the
        function resolves, and it cannot dangle. See aws/aws-lambda-builders#935.
        """
        # Own directory last, and resolved into one mapping before linking: create_symlink_or_copy keeps
        # the first link at a destination, so linking as we go would give the hoisted copy precedence.
        chosen = {}
        for directory in (self._project_root, self._install_dir):
            tree = os.path.join(directory, "node_modules")
            if not os.path.isdir(tree):
                LOG.debug("NODEJS no dependencies installed in %s, nothing to link from there", tree)
                continue
            LOG.debug("NODEJS linking every package installed in %s into the artifacts", tree)
            chosen.update(dict(self._installed_packages(tree)))

        if not chosen:
            LOG.warning(
                "No installed dependencies were found for %s; the artifacts will have no node_modules",
                self._install_dir,
            )
        for name, package_dir in chosen.items():
            self._link(package_dir, destination, name)

    def _installed_packages(self, tree):
        """
        `(name, directory)` for every package directly inside one `node_modules`, scopes walked one level.

        Dot entries are npm's bookkeeping (`.package-lock.json`, `.bin`), not packages.
        """
        for entry in sorted(os.listdir(tree)):
            if entry.startswith("."):
                continue
            path = os.path.join(tree, entry)
            if entry.startswith("@"):
                if os.path.isdir(path):
                    for scoped in sorted(os.listdir(path)):
                        if not scoped.startswith("."):
                            yield f"{entry}/{scoped}", os.path.join(path, scoped)
                continue
            yield entry, path

    def _packages_by_name(self, package_dirs):
        """
        Map each package to the one name it will be linked under, resolving same-name collisions.

        A function pinning its own copy of a package the root also hoists produces two paths wanting one
        name; the function's own wins, since that is what its code resolves. See
        aws/aws-lambda-builders#935 for why nesting cannot decide this.
        """
        chosen = {}
        for package_dir in package_dirs:
            name = self._link_name(package_dir)
            if name in chosen:
                if self._is_inside(package_dir, self._install_dir):
                    LOG.debug("NODEJS %s pins its own %s; it wins over %s", self._install_dir, name, chosen[name])
                    chosen[name] = package_dir
                else:
                    # Neither copy is the function's own, so this rule cannot say which should win.
                    LOG.warning(
                        "Two installed copies of %s claim the same name; keeping %s and ignoring %s",
                        name,
                        chosen[name],
                        package_dir,
                    )
                continue
            chosen[name] = package_dir
        return chosen

    def _link_name(self, package_dir):
        """
        The name node must find this package under: the segments after the last `node_modules`, scope
        included.

        From the path, not the manifest - an npm alias makes the two differ, and a dependency's manifest
        is untrusted input to a path. Outside `node_modules` (a workspace dependency, reported as its own
        source directory) the manifest is the only source. See aws/aws-lambda-builders#935.
        """
        segments = os.path.normpath(package_dir).split(os.sep)
        for index in range(len(segments) - 1, -1, -1):
            if os.path.normcase(segments[index]) == "node_modules":
                return self._validated_name("/".join(segments[index + 1 :]), package_dir)

        try:
            name = self._osutils.parse_json(os.path.join(package_dir, "package.json"))["name"]
        except (OSError, ValueError, KeyError) as ex:
            # no readable manifest and no name in the path; guessing one lands it where node will not look
            raise ActionFailedError(f"Cannot read the package name of {package_dir}: {ex}")
        return self._validated_name(name, package_dir)

    @staticmethod
    def _validated_name(name, package_dir):
        if not isinstance(name, str) or not NODE_MODULES_PACKAGE_NAME.match(name):
            raise ActionFailedError(f"{package_dir} claims the unusable package name {name!r}")
        return name

    def _link(self, package_dir, destination, name):
        link_path = os.path.join(destination, *name.split("/"))
        # Second guard behind NODE_MODULES_PACKAGE_NAME. Resolve the PARENT and normalise, not the link
        # itself: realpath follows an existing link to its target outside the artifacts, and commonpath
        # does not interpret a trailing `..`. See aws/aws-lambda-builders#935.
        real_destination = os.path.realpath(destination)
        landing = os.path.normpath(
            os.path.join(os.path.realpath(os.path.dirname(link_path)), os.path.basename(link_path))
        )
        try:
            contained = os.path.commonpath([real_destination, landing]) == real_destination
        except ValueError:
            # different drives on Windows, which is an escape rather than an error to pass on
            contained = False
        if not contained:
            raise ActionFailedError(f"{package_dir} would be linked outside the artifacts as {name!r}")
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        utils.create_symlink_or_copy(package_dir, link_path)

    @staticmethod
    def _is_inside(path, directory):
        parent = os.path.normcase(os.path.realpath(directory))
        return os.path.normcase(os.path.realpath(path)).startswith(parent + os.sep)

    def _outermost_packages(self, closure):
        """
        Keep the packages that need their own entry in node_modules.

        npm reports the project itself, which is not one of its own dependencies, and it reports a nested
        copy of a package that a dependency pins to a different version. A nested copy must stay where it
        is - hoisting it would shadow the top-level version for every other caller - and it is already
        reachable through the dependency that contains it, so only the outermost paths are linked.
        """
        # Compare through normcase, link the original path: an `npm ls` closure carries npm's spelling
        # while project_root and install_dir carry the build's, and on Windows those can differ in case
        # and still name one directory. See aws/aws-lambda-builders#935.
        paths = [os.path.realpath(path) for path in closure]
        excluded = {os.path.normcase(os.path.realpath(d)) for d in (self._project_root, self._install_dir)}
        candidates = [path for path in paths if os.path.normcase(path) not in excluded]

        def is_nested_in_another(path):
            key = os.path.normcase(path)
            return any(
                key != os.path.normcase(other) and key.startswith(os.path.normcase(other) + os.sep)
                for other in candidates
            )

        return [path for path in candidates if not is_nested_in_another(path)]
