import sys
import os
import zipfile
import tarfile
import io
from collections import defaultdict, namedtuple
from unittest import TestCase, mock

import pytest

from aws_lambda_builders.architecture import ARM64
from aws_lambda_builders.workflows.python_pip.packager import PipRunner, UnsupportedPackageError
from aws_lambda_builders.workflows.python_pip.packager import DependencyBuilder
from aws_lambda_builders.workflows.python_pip.packager import Package
from aws_lambda_builders.workflows.python_pip.packager import MissingDependencyError
from aws_lambda_builders.workflows.python_pip.packager import SubprocessPip
from aws_lambda_builders.workflows.python_pip.packager import SDistMetadataFetcher
from aws_lambda_builders.workflows.python_pip.packager import InvalidSourceDistributionNameError
from aws_lambda_builders.workflows.python_pip.packager import get_lambda_abi
from aws_lambda_builders.workflows.python_pip.compat import pip_no_compile_c_env_vars
from aws_lambda_builders.workflows.python_pip.compat import pip_no_compile_c_shim
from aws_lambda_builders.workflows.python_pip.utils import OSUtils


FakePipCall = namedtuple("FakePipEntry", ["args", "env_vars", "shim"])


def _create_app_structure(tmpdir):
    appdir = tmpdir.mkdir("app")
    appdir.join("app.py").write("# Test app")
    return appdir


@pytest.fixture
def sdist_reader():
    # We are removing references to sys.executable from the business logic but are using it here for testing purposes
    return SDistMetadataFetcher(python_exe=sys.executable)


@pytest.fixture
def sdist_builder():
    s = FakeSdistBuilder()
    return s


class FakeSdistBuilder(object):
    _SETUP_PY = "from setuptools import setup\n" "setup(\n" '    name="%s",\n' '    version="%s"\n' ")\n"

    def write_fake_sdist(self, directory, name, version):
        filename = "%s-%s.zip" % (name, version)
        path = "%s/%s" % (directory, filename)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("sdist/setup.py", self._SETUP_PY % (name, version))
        return directory, filename


class PathArgumentEndingWith(object):
    def __init__(self, filename):
        self._filename = filename

    def __eq__(self, other):
        if isinstance(other, str):
            filename = os.path.split(other)[-1]
            return self._filename == filename
        return False


class FakePip(object):
    def __init__(self):
        self._calls = defaultdict(lambda: [])
        self._call_history = []
        self._side_effects = defaultdict(lambda: [])
        self._return_tuple = (0, b"", b"")

    def main(self, args, env_vars=None, shim=None):
        cmd, args = args[0], args[1:]
        self._calls[cmd].append((args, env_vars, shim))
        try:
            side_effects = self._side_effects[cmd].pop(0)
            for side_effect in side_effects:
                self._call_history.append(
                    (
                        FakePipCall(args, env_vars, shim),
                        FakePipCall(
                            side_effect.expected_args, side_effect.expected_env_vars, side_effect.expected_shim
                        ),
                    )
                )
                side_effect.execute(args)
        except IndexError:
            pass
        return self._return_tuple

    def set_return_tuple(self, rc, out, err):
        self._return_tuple = (rc, out, err)

    def packages_to_download(self, expected_args, packages, whl_contents=None):
        side_effects = [PipSideEffect(pkg, "--dest", expected_args, whl_contents) for pkg in packages]
        self._side_effects["download"].append(side_effects)

    def wheels_to_build(self, expected_args, wheels_to_build, expected_env_vars=None, expected_shim=None):
        # The SubprocessPip class handles injecting the
        # subprocess_python_base_environ into the env vars if needed,
        # so at this level of abstraction the env vars just default
        # to an empty dict if None is provided.
        if expected_env_vars is None:
            expected_env_vars = {}
        if expected_shim is None:
            expected_shim = ""
        side_effects = [
            PipSideEffect(
                pkg, "--wheel-dir", expected_args, expected_env_vars=expected_env_vars, expected_shim=expected_shim
            )
            for pkg in wheels_to_build
        ]
        self._side_effects["wheel"].append(side_effects)

    @property
    def calls(self):
        return self._calls

    def validate(self):
        for calls in self._call_history:
            actual_call, expected_call = calls
            assert actual_call.args == expected_call.args
            assert actual_call.env_vars == expected_call.env_vars
            assert actual_call.shim == expected_call.shim


class PipSideEffect(object):
    def __init__(self, filename, dirarg, expected_args, whl_contents=None, expected_env_vars=None, expected_shim=None):
        self._filename = filename
        self._package_name = filename.split("-")[0]
        self._dirarg = dirarg
        self.expected_args = expected_args
        self.expected_env_vars = expected_env_vars
        self.expected_shim = expected_shim
        if whl_contents is None:
            whl_contents = ["{package_name}/placeholder"]
        self._whl_contents = whl_contents

    def _build_fake_whl(self, directory, filename):
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            package = Package(directory, filename, python_exe=sys.executable)
            with zipfile.ZipFile(filepath, "w") as z:
                for content_path in self._whl_contents:
                    z.writestr(content_path.format(package_name=self._package_name, data_dir=package.data_dir), b"")

    def _build_fake_sdist(self, filepath):
        # tar.gz is the same no reason to test it here as it is tested in
        # unit.deploy.TestSdistMetadataFetcher
        assert filepath.endswith(".zip")
        components = os.path.split(filepath)
        prefix, filename = components[:-1], components[-1]
        directory = os.path.join(*prefix)
        filename_without_ext = filename[:-4]
        pkg_name, pkg_version = filename_without_ext.split("-")
        builder = FakeSdistBuilder()
        builder.write_fake_sdist(directory, pkg_name, pkg_version)

    def execute(self, args):
        """Generate the file in the target_dir."""
        if self._dirarg:
            target_dir = None
            for i, arg in enumerate(args):
                if arg == self._dirarg:
                    target_dir = args[i + 1]
            if target_dir:
                filepath = os.path.join(target_dir, self._filename)
                if filepath.endswith(".whl"):
                    self._build_fake_whl(target_dir, self._filename)
                else:
                    self._build_fake_sdist(filepath)


@pytest.fixture
def osutils():
    return OSUtils()


@pytest.fixture
def empty_env_osutils():
    class EmptyEnv(object):
        def original_environ(self):
            return {}

    return EmptyEnv()


@pytest.fixture
def pip_runner(empty_env_osutils):
    pip = FakePip()
    pip_runner = PipRunner(python_exe=sys.executable, pip=pip, osutils=empty_env_osutils)
    return pip, pip_runner


class TestDependencyBuilder(object):
    def _write_requirements_txt(self, packages, directory):
        contents = "\n".join(packages)
        filepath = os.path.join(directory, "requirements.txt")
        with open(filepath, "w") as f:
            f.write(contents)

    def _make_appdir_and_dependency_builder(self, reqs, tmpdir, runner, runtime="python3.9", **kwargs):
        appdir = str(_create_app_structure(tmpdir))
        self._write_requirements_txt(reqs, appdir)
        builder = DependencyBuilder(OSUtils(), runtime, sys.executable, runner, **kwargs)
        return appdir, builder

    def test_can_build_local_dir_as_whl(self, tmpdir, pip_runner, osutils):
        reqs = ["../foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.set_return_tuple(0, (b"Processing ../foo\n" b"  Link is a directory," b" ignoring download_dir"), b"")
        pip.wheels_to_build(
            expected_args=["--no-deps", "--wheel-dir", mock.ANY, "../foo"],
            wheels_to_build=["foo-1.2-cp39-none-any.whl"],
        )

        site_packages = os.path.join(appdir, "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        assert ["foo"] == installed_packages

    def test_can_get_whls_all_manylinux(self, tmpdir, pip_runner, osutils):
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl", "bar-1.2-cp39-cp39-manylinux1_x86_64.whl"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_use_abi3_whl_for_any_python3(self, tmpdir, pip_runner, osutils):
        reqs = ["foo", "bar", "baz", "qux"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=[
                "foo-1.2-cp33-abi3-manylinux1_x86_64.whl",
                "bar-1.2-cp34-abi3-manylinux1_x86_64.whl",
                "baz-1.2-cp35-abi3-manylinux1_x86_64.whl",
                "qux-1.2-cp36-abi3-manylinux1_x86_64.whl",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_expand_purelib_whl(self, tmpdir, pip_runner, osutils):
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=["foo-1.2.data/purelib/foo/"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_expand_platlib_whl(self, tmpdir, pip_runner, osutils):
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=["foo-1.2.data/platlib/foo/"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_expand_platlib_and_purelib(self, tmpdir, pip_runner, osutils):
        # This wheel installs two importable libraries foo and bar, one from
        # the wheels purelib and one from its platlib.
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=["foo-1.2.data/platlib/foo/", "foo-1.2.data/purelib/bar/"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_does_ignore_data(self, tmpdir, pip_runner, osutils):
        # Make sure the wheel installer does not copy the data directory
        # up to the root.
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=["foo/placeholder", "foo-1.2.data/data/bar/"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages
        assert "bar" not in installed_packages

    def test_does_ignore_include(self, tmpdir, pip_runner, osutils):
        # Make sure the wheel installer does not copy the includes directory
        # up to the root.
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=["foo/placeholder", "foo.1.2.data/includes/bar/"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages
        assert "bar" not in installed_packages

    def test_does_ignore_scripts(self, tmpdir, pip_runner, osutils):
        # Make sure the wheel isntaller does not copy the scripts directory
        # up to the root.
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=["{package_name}/placeholder", "{data_dir}/scripts/bar/placeholder"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages
        assert "bar" not in installed_packages

    def test_can_expand_platlib_and_platlib_and_root(self, tmpdir, pip_runner, osutils):
        # This wheel installs three import names foo, bar and baz.
        # they are from the root install directory and the platlib and purelib
        # subdirectories in the platlib.
        reqs = ["foo", "bar", "baz"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2-cp39-cp39-manylinux1_x86_64.whl"],
            whl_contents=[
                "{package_name}/placeholder",
                "{data_dir}/platlib/bar/placeholder",
                "{data_dir}/purelib/baz/placeholder",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_get_whls_mixed_compat(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar", "baz"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=[
                "foo-1.0-cp39-none-any.whl",
                "bar-1.2-cp39-cp39-manylinux1_x86_64.whl",
                "baz-1.5-cp39-cp39-linux_x86_64.whl",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_support_pep_600_tags(self, tmpdir, osutils, pip_runner):
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=[
                "foo-1.2-cp39-cp39-manylinux_2_12_x86_64.whl",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_support_compressed_tags(self, tmpdir, osutils, pip_runner):
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=[
                "foo-1.2-cp39-cp39-manylinux_2_5_x86_64.manylinux1_x86_64.whl",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_get_arm64_whls(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar", "baz"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner, architecture=ARM64)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=[
                "foo-1.0-cp39-none-any.whl",
                "bar-1.2-cp39-none-manylinux2014_aarch64.whl",
                "baz-1.5-cp39-cp39-manylinux2014_aarch64.whl",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_get_newer_platforms(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner, runtime="python3.12")
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.0-cp312-none-any.whl", "bar-1.2-cp312-cp312-manylinux_2_28_x86_64.whl"],
        )
        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_can_get_newer_platforms_cross_compile(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(
            reqs, tmpdir, runner, runtime="python3.12", architecture=ARM64
        )
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.0-cp312-none-any.whl", "bar-1.2-cp312-cp312-manylinux_2_28_x86_64.whl"],
        )

        # First call returned x86_64 wheels, fallback to the second call
        pip.packages_to_download(
            expected_args=[
                "--only-binary=:all:",
                "--no-deps",
                "--platform",
                "any",
                "--platform",
                "linux_aarch64",
                "--platform",
                "manylinux2014_aarch64",
                "--platform",
                "manylinux_2_17_aarch64",
                # It's python 3.12, so we can use newer platforms.
                "--platform",
                "manylinux_2_28_aarch64",
                "--platform",
                "manylinux_2_34_aarch64",
                "--implementation",
                "cp",
                "--abi",
                get_lambda_abi(builder.runtime),
                "--dest",
                mock.ANY,
                "bar==1.2",
            ],
            packages=["bar-1.2-cp312-cp312-manylinux_2_28_aarch64.whl"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_does_fail_on_invalid_local_package(self, tmpdir, osutils, pip_runner):
        reqs = ["../foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.set_return_tuple(0, (b"Processing ../foo\n" b"  Link is a directory," b" ignoring download_dir"), b"")
        pip.wheels_to_build(
            expected_args=["--no-deps", "--wheel-dir", mock.ANY, "../foo"],
            wheels_to_build=["foo-1.2-cp36-cp36m-macosx_10_6_intel.whl"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            with pytest.raises(MissingDependencyError) as e:
                builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)
        missing_packages = list(e.value.missing)

        pip.validate()
        assert len(missing_packages) == 1
        assert missing_packages[0].identifier == "foo==1.2"
        assert len(installed_packages) == 0

    def test_does_fail_on_narrow_py27_unicode(self, tmpdir, osutils, pip_runner):
        reqs = ["baz"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["baz-1.5-cp27-cp27m-linux_x86_64.whl"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            with pytest.raises(MissingDependencyError) as e:
                builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        missing_packages = list(e.value.missing)
        pip.validate()
        assert len(missing_packages) == 1
        assert missing_packages[0].identifier == "baz==1.5"
        assert len(installed_packages) == 0

    def test_does_fail_on_python_1_whl(self, tmpdir, osutils, pip_runner):
        reqs = ["baz"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["baz-1.5-cp14-cp14m-linux_x86_64.whl"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            with pytest.raises(MissingDependencyError) as e:
                builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        missing_packages = list(e.value.missing)
        pip.validate()
        assert len(missing_packages) == 1
        assert missing_packages[0].identifier == "baz==1.5"
        assert len(installed_packages) == 0

    def test_does_fail_on_pep_600_tag_with_unsupported_glibc_version(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar", "baz", "qux"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=[
                "foo-1.2-cp39-cp39-manylinux_2_12_x86_64.whl",
                "bar-1.2-cp39-cp39-manylinux_2_999_x86_64.whl",
                "baz-1.2-cp39-cp39-manylinux_3_12_x86_64.whl",
                "qux-1.2-cp39-cp39-manylinux_3_999_x86_64.whl",
            ],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            with pytest.raises(MissingDependencyError) as e:
                builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        missing_packages = list(e.value.missing)
        pip.validate()
        assert len(missing_packages) == 3
        missing_package_identifies = [package.identifier for package in missing_packages]
        assert "bar==1.2" in missing_package_identifies
        assert "baz==1.2" in missing_package_identifies
        assert "qux==1.2" in missing_package_identifies
        assert len(installed_packages) == 1

    def test_can_replace_incompat_whl(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.0-cp39-none-any.whl", "bar-1.2-cp39-cp39-macosx_10_6_intel.whl"],
        )
        # Once the initial download has 1 incompatible whl file. The second,
        # more targeted download, finds manylinux1_x86_64 and downloads that.
        pip.packages_to_download(
            expected_args=[
                "--only-binary=:all:",
                "--no-deps",
                "--platform",
                "any",
                "--platform",
                "linux_x86_64",
                "--platform",
                "manylinux1_x86_64",
                "--platform",
                "manylinux2010_x86_64",
                "--platform",
                "manylinux2014_x86_64",
                "--platform",
                "manylinux_2_17_x86_64",
                "--implementation",
                "cp",
                "--abi",
                get_lambda_abi(builder.runtime),
                "--dest",
                mock.ANY,
                "bar==1.2",
            ],
            packages=["bar-1.2-cp39-cp39-manylinux1_x86_64.whl"],
        )
        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_allowlist_sqlalchemy(self, tmpdir, osutils, pip_runner):
        reqs = ["sqlalchemy==1.1.18"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["SQLAlchemy-1.1.18-cp36-cp36m-macosx_10_11_x86_64.whl"],
        )
        pip.packages_to_download(
            expected_args=[
                "--only-binary=:all:",
                "--no-deps",
                "--platform",
                "any",
                "--platform",
                "linux_x86_64",
                "--platform",
                "manylinux1_x86_64",
                "--platform",
                "manylinux2010_x86_64",
                "--platform",
                "manylinux2014_x86_64",
                "--platform",
                "manylinux_2_17_x86_64",
                "--implementation",
                "cp",
                "--abi",
                get_lambda_abi(builder.runtime),
                "--dest",
                mock.ANY,
                "sqlalchemy==1.1.18",
            ],
            packages=["SQLAlchemy-1.1.18-cp36-cp36m-macosx_10_11_x86_64.whl"],
        )
        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        assert installed_packages == ["SQLAlchemy"]

    def test_can_build_sdist(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2.zip", "bar-1.2-cp39-cp39-manylinux1_x86_64.whl"],
        )
        # Foo is built from and is pure python so it yields a compatible
        # wheel file.
        pip.wheels_to_build(
            expected_args=["--no-deps", "--wheel-dir", mock.ANY, PathArgumentEndingWith("foo-1.2.zip")],
            wheels_to_build=["foo-1.2-cp39-none-any.whl"],
        )
        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        pip.validate()
        for req in reqs:
            assert req in installed_packages

    def test_build_sdist_makes_incompatible_whl(self, tmpdir, osutils, pip_runner):
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2.zip", "bar-1.2-cp39-cp39-manylinux1_x86_64.whl"],
        )
        # foo is compiled since downloading it failed to get any wheels. And
        # the second download for manylinux1_x86_64 wheels failed as well.
        # building in this case yields a platform specific wheel file that is
        # not compatible. In this case currently there is nothing that chalice
        # can do to install this package.
        pip.wheels_to_build(
            expected_args=["--no-deps", "--wheel-dir", mock.ANY, PathArgumentEndingWith("foo-1.2.zip")],
            wheels_to_build=["foo-1.2-cp39-cp39-macosx_10_6_intel.whl"],
        )
        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            with pytest.raises(MissingDependencyError) as e:
                builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        # bar should succeed and foo should failed.
        missing_packages = list(e.value.missing)
        pip.validate()
        assert len(missing_packages) == 1
        assert missing_packages[0].identifier == "foo==1.2"
        assert installed_packages == ["bar"]

    def test_can_build_package_with_optional_c_speedups_and_no_wheel(self, tmpdir, osutils, pip_runner):
        reqs = ["foo"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        # In this scenario we are downloading a package that has no wheel files
        # at all, and optional c speedups. The initial download will yield an
        # sdist since there were no wheels.
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2.zip"],
        )

        # Chalice should now try and build this into a wheel file. Since it has
        # optional c speedups it will build a platform dependent wheel file
        # which is not compatible with lambda.
        pip.wheels_to_build(
            expected_args=["--no-deps", "--wheel-dir", mock.ANY, PathArgumentEndingWith("foo-1.2.zip")],
            wheels_to_build=["foo-1.2-cp36-cp36m-macosx_10_6_intel.whl"],
        )

        # Now chalice should make a last ditch effort to build the package by
        # trying once again to build the sdist, but this time it will prevent
        # c extensions from compiling by force. If the package had optional
        # c speedups (which in this scenario it did) then it will
        # successfully fall back to building a pure python wheel file.
        pip.wheels_to_build(
            expected_args=["--no-deps", "--wheel-dir", mock.ANY, PathArgumentEndingWith("foo-1.2.zip")],
            expected_env_vars=pip_no_compile_c_env_vars,
            expected_shim=pip_no_compile_c_shim,
            wheels_to_build=["foo-1.2-cp36-none-any.whl"],
        )

        site_packages = os.path.join(appdir, ".chalice.", "site-packages")
        with osutils.tempdir() as scratch_dir:
            builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        # Now we should have successfully built the foo package.
        pip.validate()
        assert installed_packages == ["foo"]

    def test_build_into_existing_dir_with_preinstalled_packages(self, tmpdir, osutils, pip_runner):
        # Same test as above so we should get foo failing and bar succeeding
        # but in this test we started with a .chalice/site-packages directory
        # with both foo and bar already installed. It should still fail since
        # they may be there by happenstance, or from an incompatible version
        # of python.
        reqs = ["foo", "bar"]
        pip, runner = pip_runner
        appdir, builder = self._make_appdir_and_dependency_builder(reqs, tmpdir, runner)
        requirements_file = os.path.join(appdir, "requirements.txt")
        pip.packages_to_download(
            expected_args=["-r", requirements_file, "--dest", mock.ANY, "--exists-action", "i"],
            packages=["foo-1.2.zip", "bar-1.2-cp39-cp39-manylinux1_x86_64.whl"],
        )
        pip.packages_to_download(
            expected_args=[
                "--only-binary=:all:",
                "--no-deps",
                "--platform",
                "any",
                "--platform",
                "linux_x86_64",
                "--platform",
                "manylinux1_x86_64",
                "--platform",
                "manylinux2010_x86_64",
                "--platform",
                "manylinux2014_x86_64",
                "--platform",
                "manylinux_2_17_x86_64",
                "--implementation",
                "cp",
                "--abi",
                get_lambda_abi(builder.runtime),
                "--dest",
                mock.ANY,
                "foo==1.2",
            ],
            packages=["foo-1.2-cp39-cp39-macosx_10_6_intel.whl"],
        )

        # Add two fake packages foo and bar that have previously been
        # installed in the site-packages directory.
        site_packages = os.path.join(appdir, ".chalice", "site-packages")
        foo = os.path.join(site_packages, "foo")
        os.makedirs(foo)
        bar = os.path.join(site_packages, "bar")
        os.makedirs(bar)
        with osutils.tempdir() as scratch_dir:
            with pytest.raises(MissingDependencyError) as e:
                builder.build_site_packages(requirements_file, site_packages, scratch_dir)
        installed_packages = os.listdir(site_packages)

        # bar should succeed and foo should failed.
        missing_packages = list(e.value.missing)
        pip.validate()
        assert len(missing_packages) == 1
        assert missing_packages[0].identifier == "foo==1.2"
        assert installed_packages == ["bar"]


class TestPipRunner(TestCase):
    def test_build_wheel_calls_pip_without_ld_library_path(self):
        pip_mock = mock.Mock()
        pip_mock.main.return_value = (0, "out", "err")
        os_utils_mock = mock.Mock()
        pip_runner = PipRunner(mock.Mock(), pip_mock, os_utils_mock)
        pip_runner.build_wheel("wheel", "dir")
        os_utils_mock.original_environ.assert_called_once()


class TestSubprocessPip(object):
    def test_can_invoke_pip(self):
        pip = SubprocessPip(python_exe=sys.executable)
        rc, _, _ = pip.main(["--version"])
        # Simple assertion that we can execute pip
        assert rc == 0

    def test_does_error_code_propagate(self):
        pip = SubprocessPip(python_exe=sys.executable)
        rc, _, err = pip.main(["badcommand"])
        assert rc != 0
        # Don't want to depend on a particular error message from pip since it
        # may change if we pin a differnet version to Chalice at some point.
        # But there should be a non-empty error message of some kind.
        assert err != b""


class TestSdistMetadataFetcher(object):
    _SETUPTOOLS = "from setuptools import setup"
    _DISTUTILS = "from distutils.core import setup"
    _BOTH = (
        "try:\n"
        "    from setuptools import setup\n"
        "except ImportError:\n"
        "    from distutils.core import setuptools\n"
    )

    _SETUP_PY = "%s\n" "setup(\n" '    name="%s",\n' '    version="%s"\n' ")\n"
    _VALID_TAR_FORMATS = ["tar.gz", "tar.bz2"]

    def _write_fake_sdist(self, setup_py, directory, ext, pkg_info_contents=None):
        filename = "sdist.%s" % ext
        path = "%s/%s" % (directory, filename)
        if ext == "zip":
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("sdist/setup.py", setup_py)
                if pkg_info_contents is not None:
                    z.writestr("sdist/PKG-INFO", pkg_info_contents)
        elif ext in self._VALID_TAR_FORMATS:
            compression_format = ext.split(".")[1]
            with tarfile.open(path, "w:%s" % compression_format) as tar:
                tarinfo = tarfile.TarInfo("sdist/setup.py")
                tarinfo.size = len(setup_py)
                tar.addfile(tarinfo, io.BytesIO(setup_py.encode()))
                if pkg_info_contents is not None:
                    tarinfo = tarfile.TarInfo("sdist/PKG-INFO")
                    tarinfo.size = len(pkg_info_contents)
                    tar.addfile(tarinfo, io.BytesIO(pkg_info_contents.encode()))
        else:
            open(path, "a").close()
        filepath = os.path.join(directory, filename)
        return filepath

    def test_setup_tar_gz(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._SETUPTOOLS, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_setup_tar_bz2(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._SETUPTOOLS, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.bz2")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_setup_tar_gz_hyphens_in_name(self, osutils, sdist_reader):
        # The whole reason we need to use the egg info to get the name and
        # version is that we cannot deterministically parse that information
        # from the filenames themselves. This test puts hyphens in the name
        # which would break a simple ``split("-")`` attempt to get that
        # information.
        setup_py = self._SETUP_PY % (self._SETUPTOOLS, "foo-bar", "1.2b2")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo-bar"
        assert version == "1.2b2"

    def test_setup_zip(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._SETUPTOOLS, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "zip")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_distutil_tar_gz(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._DISTUTILS, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_distutil_tar_bz2(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._DISTUTILS, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.bz2")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_distutil_zip(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._DISTUTILS, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "zip")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_both_tar_gz(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._BOTH, "foo-bar", "1.0b2")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo-bar"
        assert version == "1.0b2"

    def test_both_tar_bz2(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._BOTH, "foo-bar", "1.0b2")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.bz2")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo-bar"
        assert version == "1.0b2"

    def test_both_zip(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._BOTH, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "zip")
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_bad_format(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % (self._BOTH, "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz2")
            with pytest.raises(InvalidSourceDistributionNameError):
                name, version = sdist_reader.get_package_name_and_version(filepath)

    def test_cant_get_egg_info_filename(self, osutils, sdist_reader):
        # In this scenario the setup.py file will fail with an import
        # error so we should verify we try a fallback to look for
        # PKG-INFO.
        bad_setup_py = self._SETUP_PY % (
            "import some_build_dependency",
            "foo",
            "1.0",
        )
        pkg_info_file = "Name: foo\n" "Version: 1.0\n"
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(bad_setup_py, tempdir, "zip", pkg_info_file)
            name, version = sdist_reader.get_package_name_and_version(filepath)
        assert name == "foo"
        assert version == "1.0"

    def test_pkg_info_fallback_fails_raises_error(self, osutils, sdist_reader):
        setup_py = self._SETUP_PY % ("import build_time_dependency", "foo", "1.0")
        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz")
            with pytest.raises(UnsupportedPackageError):
                sdist_reader.get_package_name_and_version(filepath)

    def test_pkg_info_uses_fallback(self, osutils, sdist_reader):
        # similar to test_cant_get_egg_info_filename
        # but checks for UNKNOWN and/or 0.0.0 before
        # using fallback
        fallback_name = "mypkg"
        fallback_version = "1.0.0"

        setup_py = self._SETUP_PY % ("", "UNKNOWN", "0.0.0")
        fallback_pkg_info = "Name: %s\nVersion: %s\n" % (fallback_name, fallback_version)

        with osutils.tempdir() as tempdir:
            filepath = self._write_fake_sdist(setup_py, tempdir, "tar.gz", fallback_pkg_info)
            name, version = sdist_reader.get_package_name_and_version(filepath)

            assert name == fallback_name
            assert version == fallback_version


class TestPackage(object):
    def test_same_pkg_sdist_and_wheel_collide(self, osutils, sdist_builder):
        with osutils.tempdir() as tempdir:
            sdist_builder.write_fake_sdist(tempdir, "foobar", "1.0")
            pkgs = set()
            pkgs.add(Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable))
            pkgs.add(Package(tempdir, "foobar-1.0.zip", python_exe=sys.executable))
            assert len(pkgs) == 1

    def test_ensure_sdist_name_normalized_for_comparison(self, osutils, sdist_builder):
        with osutils.tempdir() as tempdir:
            sdist_builder.write_fake_sdist(tempdir, "Foobar", "1.0")
            pkgs = set()
            pkgs.add(Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable))
            pkgs.add(Package(tempdir, "Foobar-1.0.zip", python_exe=sys.executable))
            assert len(pkgs) == 1

    def test_ensure_wheel_name_normalized_for_comparison(self, osutils, sdist_builder):
        with osutils.tempdir() as tempdir:
            sdist_builder.write_fake_sdist(tempdir, "foobar", "1.0")
            pkgs = set()
            pkgs.add(Package("", "Foobar-1.0-py3-none-any.whl", python_exe=sys.executable))
            pkgs.add(Package(tempdir, "foobar-1.0.zip", python_exe=sys.executable))
            assert len(pkgs) == 1
