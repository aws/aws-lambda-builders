"""
Installs packages using PIP
"""

import sys
import re
import subprocess
import logging
from email.parser import FeedParser

from aws_lambda_builders.architecture import ARM64, X86_64
from .compat import pip_import_string
from .compat import pip_no_compile_c_env_vars
from .compat import pip_no_compile_c_shim
from .utils import OSUtils

LOG = logging.getLogger(__name__)


# TODO update the wording here
MISSING_DEPENDENCIES_TEMPLATE = r"""
Could not install dependencies:
%s
You will have to build these yourself and vendor them in
the vendor folder.
"""


class PackagerError(Exception):
    pass


class InvalidSourceDistributionNameError(PackagerError):
    pass


class RequirementsFileNotFoundError(PackagerError):
    """
    Exceptions is no longer raised.
    Keeping it here because this exception is 'public' and could still be used by a customer.
    """

    def __init__(self, requirements_path):
        super(RequirementsFileNotFoundError, self).__init__("Requirements file not found: %s" % requirements_path)


class MissingDependencyError(PackagerError):
    """Raised when some dependencies could not be packaged for any reason."""

    def __init__(self, missing):
        self.missing = missing


class NoSuchPackageError(PackagerError):
    """Raised when a package name or version could not be found."""

    def __init__(self, package_name):
        super(NoSuchPackageError, self).__init__("Could not satisfy the requirement: %s" % package_name)


class PackageDownloadError(PackagerError):
    """Generic networking error during a package download."""

    pass


class UnsupportedPackageError(Exception):
    """Unable to parse package metadata."""

    def __init__(self, package_name):
        # type: (str) -> None
        super(UnsupportedPackageError, self).__init__("Unable to retrieve name/version for package: %s" % package_name)


class UnsupportedPythonVersion(PackagerError):
    """Generic networking error during a package download."""

    def __init__(self, version):
        super(UnsupportedPythonVersion, self).__init__("'%s' version of python is not supported" % version)


def get_lambda_abi(runtime):
    supported = {
        "python3.6": "cp36m",
        "python3.7": "cp37m",
        "python3.8": "cp38",
        "python3.9": "cp39",
    }

    if runtime not in supported:
        raise UnsupportedPythonVersion(runtime)

    return supported[runtime]


class PythonPipDependencyBuilder(object):
    def __init__(self, runtime, osutils=None, dependency_builder=None, architecture=X86_64):
        """Initialize a PythonPipDependencyBuilder.

        :type runtime: str
        :param runtime: Python version to build dependencies for. This can
            either be python3.6, python3.7, python3.8 or python3.9. These are currently the
            only supported values.

        :type osutils: :class:`lambda_builders.utils.OSUtils`
        :param osutils: A class used for all interactions with the
            outside OS.

        :type dependency_builder: :class:`DependencyBuilder`
        :param dependency_builder: This class will be used to build the
            dependencies of the project.

        :type architecture: str
        :param description: Architecture used to build dependencies for. This can
        be either arm64 or x86_64. The default value is x86_64 if it's not provided.
        """
        self.osutils = osutils
        if osutils is None:
            self.osutils = OSUtils()

        if dependency_builder is None:
            dependency_builder = DependencyBuilder(self.osutils, runtime, architecture=architecture)
        self._dependency_builder = dependency_builder

    def build_dependencies(self, artifacts_dir_path, scratch_dir_path, requirements_path, ui=None, config=None):
        """Builds a python project's dependencies into an artifact directory.

        :type artifacts_dir_path: str
        :param artifacts_dir_path: Directory to write dependencies into.

        :type scratch_dir_path: str
        :param scratch_dir_path: Directory to write temp files into.

        :type requirements_path: str
        :param requirements_path: Path to a requirements.txt file to inspect
            for a list of dependencies.

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
        # TODO: The DependencyBuilder makes the assumption that it is running
        # in a virtual environment that matches the runtime you want to use.
        # Since otherwise there is no way to force pip to build wheels for the
        # correct version of python. We need to enforce that assumption here
        # by finding/creating a virtualenv of the correct version and when
        # pip is called set the appropriate env vars.

        self._dependency_builder.build_site_packages(requirements_path, artifacts_dir_path, scratch_dir_path)


class DependencyBuilder(object):
    """Build site-packages by manually downloading and unpacking wheels.

    Pip is used to download all the dependency sdists. Then wheels that
    compatible with lambda are downloaded. Any source packages that do not
    have a matching wheel file are built into a wheel and that file is checked
    for compatibility with the lambda python runtime environment.

    All compatible wheels that are downloaded/built this way are unpacked
    into a site-packages directory, to be included in the bundle by the
    packager.
    """

    _COMPATIBLE_PLATFORM_ARM64 = {
        "any",
        "linux_aarch64",
        "manylinux2014_aarch64",
    }

    _COMPATIBLE_PLATFORM_X86_64 = {
        "any",
        "linux_x86_64",
        "manylinux1_x86_64",
        "manylinux2010_x86_64",
        "manylinux2014_x86_64",
    }

    _COMPATIBLE_PLATFORMS = {
        ARM64: _COMPATIBLE_PLATFORM_ARM64,
        X86_64: _COMPATIBLE_PLATFORM_X86_64,
    }

    _MANYLINUX_LEGACY_MAP = {
        "manylinux1_x86_64": "manylinux_2_5_x86_64",
        "manylinux2010_x86_64": "manylinux_2_12_x86_64",
        "manylinux2014_x86_64": "manylinux_2_17_x86_64",
    }

    _COMPATIBLE_PACKAGE_ALLOWLIST = {"sqlalchemy"}

    # Mapping of abi to glibc version in Lambda runtime.
    _RUNTIME_GLIBC = {
        "cp27mu": (2, 17),
        "cp36m": (2, 17),
        "cp37m": (2, 17),
        "cp38": (2, 26),
        "cp39": (2, 26),
    }
    # Fallback version if we're on an unknown python version
    # not in _RUNTIME_GLIBC.
    # Unlikely to hit this case.
    _DEFAULT_GLIBC = (2, 17)

    def __init__(self, osutils, runtime, pip_runner=None, architecture=X86_64):
        """Initialize a DependencyBuilder.

        :type osutils: :class:`lambda_builders.utils.OSUtils`
        :param osutils: A class used for all interactions with the
            outside OS.

        :type runtime: str
        :param runtime: AWS Lambda Python runtime to build for

        :type pip_runner: :class:`PipRunner`
        :param pip_runner: This class is responsible for executing our pip
            on our behalf.

        :type architecture: str
        :param architecture: Architecture to build for.
        """
        self._osutils = osutils
        if pip_runner is None:
            pip_runner = PipRunner(python_exe=None, pip=SubprocessPip(osutils))
        self._pip = pip_runner
        self.runtime = runtime
        self.architecture = architecture

    def build_site_packages(self, requirements_filepath, target_directory, scratch_directory):
        """Build site-packages directory for a set of requiremetns.

        :type requirements_filepath: str
        :param requirement_filepath: The path to a requirements file to inspect
            for a list of top-level requirements to install. This should be
            equivilent to ``pip install -r requirements_filepath.txt`` in
            theory.

        :type target_directory: str
        :param target_directory: The directory to build all dependencies into.
            This directory should be on the PYTHON_PATH of whichever process
            wants to use thse dependencies.

        :type scratch_directory: str
        :param scratch_directory: The directory to write temp files into.

        :raises MissingDependencyError: This exception is raised if one or more
            packages could not be installed. The complete list of missing
            packages is included in the error object's ``missing`` property.
        """
        if self._has_at_least_one_package(requirements_filepath):
            wheels, packages_without_wheels = self._download_dependencies(scratch_directory, requirements_filepath)
            self._install_wheels(scratch_directory, target_directory, wheels)
            if packages_without_wheels:
                raise MissingDependencyError(packages_without_wheels)

    def _has_at_least_one_package(self, filename):
        if not self._osutils.file_exists(filename):
            return False
        with open(filename, "r") as f:
            # This is meant to be a best effort attempt.
            # This can return True and still have no packages
            # actually being specified, but those aren't common
            # cases.
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return True
        return False

    def _download_dependencies(self, directory, requirements_filename):
        # Download all dependencies we can, letting pip choose what to
        # download.
        # deps should represent the best effort we can make to gather all the
        # dependencies.
        deps = self._download_all_dependencies(requirements_filename, directory)

        # Sort the downloaded packages into three categories:
        # - sdists (Pip could not get a wheel so it gave us an sdist)
        # - lambda compatible wheel files
        # - lambda incompatible wheel files
        # Pip will give us a wheel when it can, but some distributions do not
        # ship with wheels at all in which case we will have an sdist for it.
        # In some cases a platform specific wheel file may be availble so pip
        # will have downloaded that, if our platform does not match the
        # platform that the function will run on (x86_64 or arm64) then the
        # downloaded wheel file may not be compatible with Lambda. Pure python
        # wheels still will be compatible because they have no platform
        # dependencies.
        compatible_wheels = set()
        incompatible_wheels = set()
        sdists = set()
        for package in deps:
            if package.dist_type == "sdist":
                sdists.add(package)
            else:
                if self._is_compatible_wheel_filename(package.filename):
                    compatible_wheels.add(package)
                else:
                    incompatible_wheels.add(package)
        LOG.debug("initial compatible: %s", compatible_wheels)
        LOG.debug("initial incompatible: %s", incompatible_wheels | sdists)

        # Next we need to go through the downloaded packages and pick out any
        # dependencies that do not have a compatible wheel file downloaded.
        # For these packages we need to explicitly try to download a
        # compatible wheel file.
        missing_wheels = sdists | incompatible_wheels
        self._download_binary_wheels(missing_wheels, directory)

        # Re-count the wheel files after the second download pass. Anything
        # that has an sdist but not a valid wheel file is still not going to
        # work on lambda and we must now try and build the sdist into a wheel
        # file ourselves.
        compatible_wheels, incompatible_wheels = self._categorize_wheel_files(directory)
        LOG.debug("compatible wheels after second download pass: %s", compatible_wheels)
        missing_wheels = sdists - compatible_wheels
        self._build_sdists(missing_wheels, directory, compile_c=True)

        # There is still the case where the package had optional C dependencies
        # for speedups. In this case the wheel file will have built above with
        # the C dependencies if it managed to find a C compiler. If we are on
        # an incompatible architecture this means the wheel file generated will
        # not be compatible. If we categorize our files once more and find that
        # there are missing dependencies we can try our last ditch effort of
        # building the package and trying to sever its ability to find a C
        # compiler.
        compatible_wheels, incompatible_wheels = self._categorize_wheel_files(directory)
        LOG.debug("compatible after building wheels (no C compiling): %s", compatible_wheels)
        missing_wheels = sdists - compatible_wheels
        self._build_sdists(missing_wheels, directory, compile_c=False)

        # Final pass to find the compatible wheel files and see if there are
        # any unmet dependencies left over. At this point there is nothing we
        # can do about any missing wheel files. We tried downloading a
        # compatible version directly and building from source.
        compatible_wheels, incompatible_wheels = self._categorize_wheel_files(directory)
        LOG.debug("compatible after building wheels (C compiling): %s", compatible_wheels)

        # Now there is still the case left over where the setup.py has been
        # made in such a way to be incompatible with python's setup tools,
        # causing it to lie about its compatibility. To fix this we have a
        # manually curated allowlist of packages that will work, despite
        # claiming otherwise.
        compatible_wheels, incompatible_wheels = self._apply_wheel_allowlist(compatible_wheels, incompatible_wheels)
        missing_wheels = deps - compatible_wheels
        LOG.debug("Final compatible: %s", compatible_wheels)
        LOG.debug("Final incompatible: %s", incompatible_wheels)
        LOG.debug("Final missing wheels: %s", missing_wheels)

        return compatible_wheels, missing_wheels

    def _download_all_dependencies(self, requirements_filename, directory):
        # Download dependencies prefering wheel files but falling back to
        # raw source dependences to get the transitive closure over
        # the dependency graph. Return the set of all package objects
        # which will serve as the primary list of dependencies needed to deploy
        # successfully.
        self._pip.download_all_dependencies(requirements_filename, directory)
        deps = {Package(directory, filename) for filename in self._osutils.get_directory_contents(directory)}
        LOG.debug("Full dependency closure: %s", deps)
        return deps

    def _download_binary_wheels(self, packages, directory):
        # Try to get binary wheels for each package that isn't compatible.
        LOG.debug("Downloading missing wheels: %s", packages)
        lambda_abi = get_lambda_abi(self.runtime)
        platform = "manylinux2014_aarch64" if self.architecture == ARM64 else "manylinux2014_x86_64"
        self._pip.download_manylinux_wheels([pkg.identifier for pkg in packages], directory, lambda_abi, platform)

    def _build_sdists(self, sdists, directory, compile_c=True):
        LOG.debug("Build missing wheels from sdists " "(C compiling %s): %s", compile_c, sdists)
        for sdist in sdists:
            path_to_sdist = self._osutils.joinpath(directory, sdist.filename)
            self._pip.build_wheel(path_to_sdist, directory, compile_c)

    def _categorize_wheel_files(self, directory):
        final_wheels = [
            Package(directory, filename)
            for filename in self._osutils.get_directory_contents(directory)
            if filename.endswith(".whl")
        ]

        compatible_wheels, incompatible_wheels = set(), set()
        for wheel in final_wheels:
            if self._is_compatible_wheel_filename(wheel.filename):
                compatible_wheels.add(wheel)
            else:
                incompatible_wheels.add(wheel)
        return compatible_wheels, incompatible_wheels

    def _is_compatible_wheel_filename(self, filename):
        wheel = filename[:-4]
        lambda_runtime_abi = get_lambda_abi(self.runtime)
        for implementation, abi, platform in self._iter_all_compatibility_tags(wheel):
            if not self._is_compatible_platform_tag(lambda_runtime_abi, platform):
                continue

            # Verify that the ABI is compatible with lambda. Either none or the
            # correct type for the python version cp27mu for py27 and cp36m for
            # py36.
            if abi == "none":
                return True
            prefix_version = implementation[:3]
            if prefix_version == "cp3":
                # Deploying python 3 function which means we need cp36m abi
                # We can also accept abi3 which is the CPython 3 Stable ABI and
                # will work on any version of python 3.
                if abi == lambda_runtime_abi or abi == "abi3":
                    return True
            elif prefix_version == "cp2":
                # Deploying to python 2 function which means we need cp27mu abi
                if abi == "cp27mu":
                    return True
        # Don't know what we have but it didn't pass compatibility tests.
        return False

    def _is_compatible_platform_tag(self, expected_abi, platform):
        """
        Verify if a platform tag is compatible based on PEP 600
        https://www.python.org/dev/peps/pep-0600/#specification

        In addition to checking the tag pattern, we also need to verify the glibc version
        """
        if platform in self._COMPATIBLE_PLATFORMS[self.architecture]:
            return True

        arch = "aarch64" if self.architecture == ARM64 else "x86_64"

        # Verify the tag pattern
        # Try to get the matching value for legacy values or keep the current
        perennial_tag = self._MANYLINUX_LEGACY_MAP.get(platform, platform)

        match = re.match("manylinux_([0-9]+)_([0-9]+)_" + arch, perennial_tag)
        if match is None:
            return False

        # Get the glibc major and minor versions and compare them with the expected ABI
        # platform: manylinux_2_17_aarch64 -> 2 and 17
        # expected_abi: cp37m -> compat glibc -> 2 and 17
        # -> Compatible
        tag_major, tag_minor = [int(x) for x in match.groups()[:2]]
        runtime_major, runtime_minor = self._RUNTIME_GLIBC.get(expected_abi, self._DEFAULT_GLIBC)

        return (tag_major, tag_minor) <= (runtime_major, runtime_minor)

    def _iter_all_compatibility_tags(self, wheel):
        """
        Generates all possible combination of tag sets as described in PEP 425
        https://www.python.org/dev/peps/pep-0425/#compressed-tag-sets
        """
        # ex: wheel = numpy-1.20.3-cp38-cp38-manylinux_2_17_aarch64.manylinux2014_aarch64
        implementation_tag, abi_tag, platform_tag = wheel.split("-")[-3:]
        # cp38, cp38, manylinux_2_17_aarch64.manylinux2014_aarch64
        for implementation in implementation_tag.split("."):
            # cp38
            for abi in abi_tag.split("."):
                # cp38
                for platform in platform_tag.split("."):
                    # manylinux_2_17_aarch64
                    # manylinux2014_aarch64
                    yield (implementation, abi, platform)

    def _apply_wheel_allowlist(self, compatible_wheels, incompatible_wheels):
        compatible_wheels = set(compatible_wheels)
        actual_incompatible_wheels = set()
        for missing_package in incompatible_wheels:
            if missing_package.name in self._COMPATIBLE_PACKAGE_ALLOWLIST:
                compatible_wheels.add(missing_package)
            else:
                actual_incompatible_wheels.add(missing_package)
        return compatible_wheels, actual_incompatible_wheels

    def _install_purelib_and_platlib(self, wheel, root):
        # Take a wheel package and the directory it was just unpacked into and
        # unpackage the purelib/platlib directories if they are present into
        # the parent directory. On some systems purelib and platlib need to
        # be installed into separate locations, for lambda this is not the case
        # and both should be installed in site-packages.
        data_dir = self._osutils.joinpath(root, wheel.data_dir)
        if not self._osutils.directory_exists(data_dir):
            return
        unpack_dirs = {"purelib", "platlib"}
        data_contents = self._osutils.get_directory_contents(data_dir)
        for content_name in data_contents:
            if content_name in unpack_dirs:
                source = self._osutils.joinpath(data_dir, content_name)
                self._osutils.copytree(source, root)
                # No reason to keep the purelib/platlib source directory around
                # so we delete it to conserve space in the package.
                self._osutils.rmtree(source)

    def _install_wheels(self, src_dir, dst_dir, wheels):
        if self._osutils.directory_exists(dst_dir):
            self._osutils.rmtree(dst_dir)
        self._osutils.makedirs(dst_dir)
        for wheel in wheels:
            zipfile_path = self._osutils.joinpath(src_dir, wheel.filename)
            self._osutils.extract_zipfile(zipfile_path, dst_dir)
            self._install_purelib_and_platlib(wheel, dst_dir)


class Package(object):
    """A class to represent a package downloaded but not yet installed."""

    def __init__(self, directory, filename, osutils=None):
        self.dist_type = "wheel" if filename.endswith(".whl") else "sdist"
        self._directory = directory
        self.filename = filename
        if osutils is None:
            osutils = OSUtils()
        self._osutils = osutils
        self._name, self._version = self._calculate_name_and_version()

    @property
    def name(self):
        return self._name

    @property
    def data_dir(self):
        # The directory format is {distribution}-{version}.data
        return "%s-%s.data" % (self._name, self._version)

    def _normalize_name(self, name):
        # Taken directly from PEP 503
        return re.sub(r"[-_.]+", "-", name).lower()

    @property
    def identifier(self):
        return "%s==%s" % (self._name, self._version)

    def __str__(self):
        return "%s(%s)" % (self.identifier, self.dist_type)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if not isinstance(other, Package):
            return False
        return self.identifier == other.identifier

    def __hash__(self):
        return hash(self.identifier)

    def _calculate_name_and_version(self):
        if self.dist_type == "wheel":
            # From the wheel spec (PEP 427)
            # {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-
            # {platform tag}.whl
            name, version = self.filename.split("-")[:2]
        else:
            info_fetcher = SDistMetadataFetcher(osutils=self._osutils)
            sdist_path = self._osutils.joinpath(self._directory, self.filename)
            name, version = info_fetcher.get_package_name_and_version(sdist_path)
        normalized_name = self._normalize_name(name)
        return normalized_name, version


class SDistMetadataFetcher(object):
    """This is the "correct" way to get name and version from an sdist."""

    # https://git.io/vQkwV
    _SETUPTOOLS_SHIM = (
        "import setuptools, tokenize;__file__=%r;"
        "f=getattr(tokenize, 'open', open)(__file__);"
        "code=f.read().replace('\\r\\n', '\\n');"
        "f.close();"
        "exec(compile(code, __file__, 'exec'))"
    )

    def __init__(self, osutils=None):
        if osutils is None:
            osutils = OSUtils()
        self._osutils = osutils

    def _parse_pkg_info_file(self, filepath):
        # The PKG-INFO generated by the egg-info command is in an email feed
        # format, so we use an email feedparser here to extract the metadata
        # from the PKG-INFO file.
        data = self._osutils.get_file_contents(filepath, binary=False)
        parser = FeedParser()
        parser.feed(data)
        return parser.close()

    def _get_pkg_info_filepath(self, package_dir):
        setup_py = self._osutils.joinpath(package_dir, "setup.py")
        script = self._SETUPTOOLS_SHIM % setup_py

        cmd = [sys.executable, "-c", script, "--no-user-cfg", "egg_info", "--egg-base", "egg-info"]
        egg_info_dir = self._osutils.joinpath(package_dir, "egg-info")
        self._osutils.makedirs(egg_info_dir)
        p = subprocess.Popen(
            cmd, cwd=package_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._osutils.original_environ()
        )
        _, stderr = p.communicate()
        info_contents = self._osutils.get_directory_contents(egg_info_dir)
        if p.returncode != 0:
            LOG.debug("Non zero rc (%s) from the setup.py egg_info command: %s", p.returncode, stderr)
        if info_contents:
            pkg_info_path = self._osutils.joinpath(egg_info_dir, info_contents[0], "PKG-INFO")
        else:
            # This might be a pep 517 package in which case this PKG-INFO file
            # should be available right in the top level directory of the sdist
            # in the case where the egg_info command fails.
            LOG.debug("Using fallback location for PKG-INFO file in package directory: %s", package_dir)
            pkg_info_path = self._osutils.joinpath(package_dir, "PKG-INFO")
        if not self._osutils.file_exists(pkg_info_path):
            raise UnsupportedPackageError(self._osutils.basename(package_dir))
        return pkg_info_path

    def _unpack_sdist_into_dir(self, sdist_path, unpack_dir):
        if sdist_path.endswith(".zip"):
            self._osutils.extract_zipfile(sdist_path, unpack_dir)
        elif sdist_path.endswith((".tar.gz", ".tar.bz2")):
            self._osutils.extract_tarfile(sdist_path, unpack_dir)
        else:
            raise InvalidSourceDistributionNameError(sdist_path)
        # There should only be one directory unpacked.
        contents = self._osutils.get_directory_contents(unpack_dir)
        return self._osutils.joinpath(unpack_dir, contents[0])

    def get_package_name_and_version(self, sdist_path):
        with self._osutils.tempdir() as tempdir:
            package_dir = self._unpack_sdist_into_dir(sdist_path, tempdir)
            pkg_info_filepath = self._get_pkg_info_filepath(package_dir)
            metadata = self._parse_pkg_info_file(pkg_info_filepath)
            name = metadata["Name"]
            version = metadata["Version"]
        return name, version


class SubprocessPip(object):
    """Wrapper around calling pip through a subprocess."""

    def __init__(self, osutils=None, python_exe=None, import_string=None):
        if osutils is None:
            osutils = OSUtils()
        self._osutils = osutils
        self.python_exe = python_exe
        if import_string is None:
            import_string = pip_import_string(python_exe=self.python_exe)
        self._import_string = import_string

    def main(self, args, env_vars=None, shim=None):
        if env_vars is None:
            env_vars = self._osutils.original_environ()
        if shim is None:
            shim = ""
        run_pip = ("import sys; %s; sys.exit(main(%s))") % (self._import_string, args)
        exec_string = "%s%s" % (shim, run_pip)
        invoke_pip = [self.python_exe, "-c", exec_string]
        p = self._osutils.popen(invoke_pip, stdout=self._osutils.pipe, stderr=self._osutils.pipe, env=env_vars)
        out, err = p.communicate()
        rc = p.returncode
        return rc, out, err


class PipRunner(object):
    """Wrapper around pip calls used by chalice."""

    # Update regex pattern to correspond with the updated output from pip
    # Specific commit:
    # https://github.com/pypa/pip/commit/b28e2c4928cc62d90b738a4613886fb1e2ad6a81#diff-5225c8e359020adb25dfc8c7a505950fd649c6c5775789c6f6517f7913f94542L529
    _LINK_IS_DIR_PATTERNS = ["Processing (.+?)\n"]

    def __init__(self, python_exe, pip, osutils=None):
        if osutils is None:
            osutils = OSUtils()
        self.python_exe = python_exe
        self._wrapped_pip = pip
        self._osutils = osutils

    def _execute(self, command, args, env_vars=None, shim=None):
        """Execute a pip command with the given arguments."""
        main_args = [command] + args
        LOG.debug("calling pip %s", " ".join(main_args))
        rc, out, err = self._wrapped_pip.main(main_args, env_vars=env_vars, shim=shim)
        return rc, out, err

    def build_wheel(self, wheel, directory, compile_c=True):
        """Build an sdist into a wheel file."""
        arguments = ["--no-deps", "--wheel-dir", directory, wheel]
        env_vars = self._osutils.environ()
        shim = ""
        if not compile_c:
            env_vars.update(pip_no_compile_c_env_vars)
            shim = pip_no_compile_c_shim
        # Ignore rc and stderr from this command since building the wheels
        # may fail and we will find out when we categorize the files that were
        # generated.
        self._execute("wheel", arguments, env_vars=env_vars, shim=shim)

    def download_all_dependencies(self, requirements_filename, directory):
        """Download all dependencies as sdist or wheel."""
        arguments = ["-r", requirements_filename, "--dest", directory, "--exists-action", "i"]
        rc, out, err = self._execute("download", arguments)
        # When downloading all dependencies we expect to get an rc of 0 back
        # since we are casting a wide net here letting pip have options about
        # what to download. If a package is not found it is likely because it
        # does not exist and was mispelled. In this case we raise an error with
        # the package name. Otherwise a nonzero rc results in a generic
        # download error where we pass along the stderr.
        if rc != 0:
            if err is None:
                err = b"Unknown error"
            error = err.decode()
            match = re.search(("Could not find a version that satisfies the " "requirement (.+?) "), error)
            if match:
                package_name = match.group(1)
                raise NoSuchPackageError(str(package_name))
            raise PackageDownloadError(error)

        # Extract local packages from pip output.
        # Iterate over possible pip outputs depending on pip version.
        stdout = out.decode()
        wheel_package_paths = set()
        for pattern in self._LINK_IS_DIR_PATTERNS:
            for match in re.finditer(pattern, stdout):
                wheel_package_paths.add(str(match.group(1)))

        for wheel_package_path in wheel_package_paths:
            # Looks odd we do not check on the error status of building the
            # wheel here. We can assume this is a valid package path since
            # we already passed the pip download stage. This stage would have
            # thrown a PackageDownloadError if any of the listed packages were
            # not valid.
            # If it fails the actual build step, it will have the same behavior
            # as any other package we fail to build a valid wheel for, and
            # complain at deployment time.
            self.build_wheel(wheel_package_path, directory)

    def download_manylinux_wheels(self, packages, directory, lambda_abi, platform="manylinux2014_x86_64"):
        """Download wheel files for manylinux for all the given packages."""
        # If any one of these dependencies fails pip will bail out. Since we
        # are only interested in all the ones we can download, we need to feed
        # each package to pip individually. The return code of pip doesn't
        # matter here since we will inspect the working directory to see which
        # wheels were downloaded. We are only interested in wheel files
        # compatible with Lambda, which depends on the function architecture,
        # and cpython implementation. The compatible abi depends on the python
        # version and is checked later.
        for package in packages:
            arguments = [
                "--only-binary=:all:",
                "--no-deps",
                "--platform",
                platform,
                "--implementation",
                "cp",
                "--abi",
                lambda_abi,
                "--dest",
                directory,
                package,
            ]
            self._execute("download", arguments)
