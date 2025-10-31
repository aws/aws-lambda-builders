import sys
from collections import namedtuple
from unittest import TestCase, mock
from unittest.mock import ANY, patch

import pytest
from parameterized import parameterized

from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.workflows.python_pip.utils import OSUtils
from aws_lambda_builders.workflows.python_pip.compat import pip_no_compile_c_env_vars
from aws_lambda_builders.workflows.python_pip.compat import pip_no_compile_c_shim
from aws_lambda_builders.workflows.python_pip.packager import DependencyBuilder, SDistMetadataFetcher
from aws_lambda_builders.workflows.python_pip.packager import PythonPipDependencyBuilder
from aws_lambda_builders.workflows.python_pip.packager import Package
from aws_lambda_builders.workflows.python_pip.packager import PipRunner
from aws_lambda_builders.workflows.python_pip.packager import SubprocessPip
from aws_lambda_builders.workflows.python_pip.packager import get_lambda_abi
from aws_lambda_builders.workflows.python_pip.packager import InvalidSourceDistributionNameError
from aws_lambda_builders.workflows.python_pip.packager import NoSuchPackageError
from aws_lambda_builders.workflows.python_pip.packager import PackageDownloadError
from aws_lambda_builders.workflows.python_pip.packager import RequirementsFileNotFoundError
from aws_lambda_builders.workflows.python_pip.packager import MissingDependencyError
from aws_lambda_builders.workflows.python_pip.packager import UnsupportedPackageError
from aws_lambda_builders.workflows.python_pip.packager import UnsupportedPythonVersion

from aws_lambda_builders.workflows.python_pip import packager

print(packager)

FakePipCall = namedtuple("FakePipEntry", ["args", "env_vars", "shim"])


class FakePip(object):
    def __init__(self):
        self._calls = []
        self._returns = []

    def main(self, args, env_vars=None, shim=None):
        self._calls.append(FakePipCall(args, env_vars, shim))
        if self._returns:
            return self._returns.pop(0)
        # Return an rc of 0 and an empty stderr and stdout
        return 0, b"", b""

    def add_return(self, return_pair):
        self._returns.append(return_pair)

    @property
    def calls(self):
        return self._calls


@pytest.fixture
def pip_factory():
    def create_pip_runner(osutils=None):
        pip = FakePip()
        pip_runner = PipRunner(python_exe=sys.executable, pip=pip, osutils=osutils)
        return pip, pip_runner

    return create_pip_runner


class CustomEnv(OSUtils):
    def __init__(self, env):
        self._env = env

    def original_environ(self):
        return self._env


@pytest.fixture
def osutils():
    return OSUtils()


class FakePopen(object):
    def __init__(self, rc, out, err):
        self.returncode = rc
        self._out = out
        self._err = err

    def communicate(self):
        return self._out, self._err


class FakePopenOSUtils(OSUtils):
    def __init__(self, processes):
        self.popens = []
        self._processes = processes

    def popen(self, *args, **kwargs):
        self.popens.append((args, kwargs))
        return self._processes.pop()


class TestExceptions(object):
    def test_requirements_file_not_found_error(self):
        error = RequirementsFileNotFoundError("/path/to/requirements.txt")
        assert str(error) == "Requirements file not found: /path/to/requirements.txt"

    def test_missing_dependency_error(self):
        missing_packages = ["package1", "package2"]
        error = MissingDependencyError(missing_packages)
        assert error.missing == missing_packages

    def test_no_such_package_error(self):
        error = NoSuchPackageError("nonexistent-package")
        assert str(error) == "Could not satisfy the requirement: nonexistent-package"

    def test_unsupported_package_error(self):
        error = UnsupportedPackageError("bad-package")
        assert str(error) == "Unable to retrieve name/version for package: bad-package"

    def test_unsupported_python_version(self):
        error = UnsupportedPythonVersion("python2.7")
        assert str(error) == "'python2.7' version of python is not supported"


class TestGetLambdaAbi(object):
    def test_get_lambda_abi_python38(self):
        assert "cp38" == get_lambda_abi("python3.8")

    def test_get_lambda_abi_python39(self):
        assert "cp39" == get_lambda_abi("python3.9")

    def test_get_lambda_abi_python310(self):
        assert "cp310" == get_lambda_abi("python3.10")

    def test_get_lambda_abi_python311(self):
        assert "cp311" == get_lambda_abi("python3.11")

    def test_get_lambda_abi_python312(self):
        assert "cp312" == get_lambda_abi("python3.12")

    def test_get_lambda_abi_python313(self):
        assert "cp313" == get_lambda_abi("python3.13")

    def test_get_lambda_abi_python314(self):
        assert "cp314" == get_lambda_abi("python3.14")

    def test_get_lambda_abi_unsupported_version(self):
        with pytest.raises(UnsupportedPythonVersion):
            get_lambda_abi("python2.7")


class TestPythonPipDependencyBuilder(object):
    def test_can_call_dependency_builder(self, osutils):
        mock_dep_builder = mock.Mock(spec=DependencyBuilder)
        osutils_mock = mock.Mock(spec=osutils)
        builder = PythonPipDependencyBuilder(
            osutils=osutils_mock, dependency_builder=mock_dep_builder, runtime="runtime", python_exe=sys.executable
        )
        builder.build_dependencies("artifacts/path/", "scratch_dir/path/", "path/to/requirements.txt")
        mock_dep_builder.build_site_packages.assert_called_once_with(
            "path/to/requirements.txt", "artifacts/path/", "scratch_dir/path/"
        )

    @mock.patch("aws_lambda_builders.workflows.python_pip.packager.DependencyBuilder")
    def test_can_create_new_dependency_builder(self, DependencyBuilderMock, osutils):
        osutils_mock = mock.Mock(spec=osutils)
        builder = PythonPipDependencyBuilder(osutils=osutils_mock, runtime="runtime", python_exe=sys.executable)
        DependencyBuilderMock.assert_called_with(osutils_mock, ANY, "runtime", architecture=X86_64)

    @mock.patch("aws_lambda_builders.workflows.python_pip.packager.DependencyBuilder")
    def test_can_call_dependency_builder_with_architecture(self, DependencyBuilderMock, osutils):
        osutils_mock = mock.Mock(spec=osutils)
        builder = PythonPipDependencyBuilder(
            osutils=osutils_mock, runtime="runtime", architecture=ARM64, python_exe=sys.executable
        )
        DependencyBuilderMock.assert_called_with(osutils_mock, ANY, "runtime", architecture=ARM64)


class TestPackage(object):
    def test_can_create_package_with_custom_osutils(self, osutils):
        pkg = Package("", "foobar-1.0-py3-none-any.whl", sys.executable, osutils)
        assert pkg._osutils == osutils

    def test_wheel_package(self):
        filename = "foobar-1.0-py3-none-any.whl"
        pkg = Package("", filename, python_exe=sys.executable)
        assert pkg.dist_type == "wheel"
        assert pkg.filename == filename
        assert pkg.identifier == "foobar==1.0"
        assert str(pkg) == "foobar==1.0(wheel)"

    def test_invalid_package(self):
        with pytest.raises(InvalidSourceDistributionNameError):
            Package("", "foobar.jpg", python_exe=sys.executable)

    def test_diff_pkg_sdist_and_whl_do_not_collide(self):
        pkgs = set()
        pkgs.add(Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable))
        pkgs.add(Package("", "badbaz-1.0-py3-none-any.whl", python_exe=sys.executable))
        assert len(pkgs) == 2

    def test_same_pkg_is_eq(self):
        pkg = Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable)
        assert pkg == pkg

    def test_pkg_is_eq_to_similar_pkg(self):
        pure_pkg = Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable)
        plat_pkg = Package("", "foobar-1.0-py3-py39-manylinux1_x86_64.whl", python_exe=sys.executable)
        assert pure_pkg == plat_pkg

    def test_pkg_is_not_equal_to_different_type(self):
        pkg = Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable)
        non_package_type = 1
        assert not (pkg == non_package_type)

    def test_pkg_repr(self):
        pkg = Package("", "foobar-1.0-py3-none-any.whl", python_exe=sys.executable)
        assert repr(pkg) == "foobar==1.0(wheel)"

    def test_wheel_data_dir(self):
        pkg = Package("", "foobar-2.0-py3-none-any.whl", python_exe=sys.executable)
        assert pkg.data_dir == "foobar-2.0.data"

    def test_can_read_packages_with_underscore_in_name(self):
        pkg = Package("", "foo_bar-2.0-py3-none-any.whl", python_exe=sys.executable)
        assert pkg.identifier == "foo-bar==2.0"

    def test_can_read_packages_with_period_in_name(self):
        pkg = Package("", "foo.bar-2.0-py3-none-any.whl", python_exe=sys.executable)
        assert pkg.identifier == "foo-bar==2.0"


class TestPipRunner(object):
    def test_does_propagate_env_vars(self, pip_factory):
        osutils = CustomEnv({"foo": "bar"})
        pip, runner = pip_factory(osutils)
        wheel = "foobar-1.2-py3-none-any.whl"
        directory = "directory"
        runner.build_wheel(wheel, directory)
        call = pip.calls[0]

        assert "foo" in call.env_vars
        assert call.env_vars["foo"] == "bar"

    def test_build_wheel(self, pip_factory):
        # Test that `pip wheel` is called with the correct params
        pip, runner = pip_factory()
        wheel = "foobar-1.0-py3-none-any.whl"
        directory = "directory"
        runner.build_wheel(wheel, directory)

        assert len(pip.calls) == 1
        call = pip.calls[0]
        assert call.args == ["wheel", "--no-deps", "--wheel-dir", directory, wheel]
        for compile_env_var in pip_no_compile_c_env_vars:
            assert compile_env_var not in call.env_vars
        assert call.shim == ""

    def test_build_wheel_without_c_extensions(self, pip_factory):
        # Test that `pip wheel` is called with the correct params when we
        # call it with compile_c=False. These will differ by platform.
        pip, runner = pip_factory()
        wheel = "foobar-1.0-py3-none-any.whl"
        directory = "directory"
        runner.build_wheel(wheel, directory, compile_c=False)

        assert len(pip.calls) == 1
        call = pip.calls[0]
        assert call.args == ["wheel", "--no-deps", "--wheel-dir", directory, wheel]
        for compile_env_var in pip_no_compile_c_env_vars:
            assert compile_env_var in call.env_vars
        assert call.shim == pip_no_compile_c_shim

    def test_download_all_deps(self, pip_factory):
        # Make sure that `pip download` is called with the correct arguments
        # for getting all sdists.
        pip, runner = pip_factory()
        runner.download_all_dependencies("requirements.txt", "directory")

        assert len(pip.calls) == 1
        call = pip.calls[0]
        assert call.args == ["download", "-r", "requirements.txt", "--dest", "directory", "--exists-action", "i"]
        assert call.env_vars is None
        assert call.shim is None

    def test_download_wheels(self, pip_factory):
        # Make sure that `pip download` is called with the correct arguments
        # for getting lambda compatible wheels.
        pip, runner = pip_factory()
        packages = ["foo", "bar", "baz"]
        runner.download_manylinux_wheels(
            packages,
            "directory",
            "abi",
            [
                "any",
                "linux_x86_64",
                "manylinux1_x86_64",
                "manylinux2010_x86_64",
                "manylinux2014_x86_64",
                "manylinux_2_17_x86_64",
            ],
        )
        expected_prefix = [
            "download",
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
            "abi",
            "--dest",
            "directory",
        ]
        for i, package in enumerate(packages):
            assert pip.calls[i].args == expected_prefix + [package]
            assert pip.calls[i].env_vars is None
            assert pip.calls[i].shim is None

    def test_download_wheels_no_wheels(self, pip_factory):
        pip, runner = pip_factory()
        runner.download_manylinux_wheels([], "directory", "abi", [])
        assert len(pip.calls) == 0

    def test_does_find_local_directory(self, pip_factory):
        pip, runner = pip_factory()
        pip.add_return((0, b"Processing ../local-dir\n", b""))
        runner.download_all_dependencies("requirements.txt", "directory")
        assert len(pip.calls) == 2
        assert pip.calls[1].args == ["wheel", "--no-deps", "--wheel-dir", "directory", "../local-dir"]

    def test_does_find_local_nested_directory(self, pip_factory):
        pip, runner = pip_factory()
        pip.add_return((0, b"Processing ../local-nested-dir (from xyz==123 and other info here)\n", b""))
        runner.download_all_dependencies("requirements.txt", "directory")
        assert len(pip.calls) == 2
        assert pip.calls[1].args == ["wheel", "--no-deps", "--wheel-dir", "directory", "../local-nested-dir"]

    def test_does_find_multiple_local_directories(self, pip_factory):
        pip, runner = pip_factory()
        pip.add_return(
            (
                0,
                (
                    b"Processing ../local-dir-1\n"
                    b"\nsome pip output...\n"
                    b"Processing ../local-dir-2\n"
                    b"  Link is a directory,"
                    b" ignoring download_dir"
                    b"Processing ../local-dir-3\n"
                ),
                b"",
            )
        )
        runner.download_all_dependencies("requirements.txt", "directory")
        pip_calls = [call.args for call in pip.calls]
        assert len(pip.calls) == 4
        assert ["wheel", "--no-deps", "--wheel-dir", "directory", "../local-dir-1"] in pip_calls
        assert ["wheel", "--no-deps", "--wheel-dir", "directory", "../local-dir-2"] in pip_calls
        assert ["wheel", "--no-deps", "--wheel-dir", "directory", "../local-dir-3"] in pip_calls

    def test_raise_no_such_package_error(self, pip_factory):
        pip, runner = pip_factory()
        pip.add_return((1, b"", (b"Could not find a version that satisfies the " b"requirement BadPackageName ")))
        with pytest.raises(NoSuchPackageError) as einfo:
            runner.download_all_dependencies("requirements.txt", "directory")
        assert str(einfo.value) == ("Could not satisfy the requirement: " "BadPackageName")

    def test_raise_other_unknown_error_during_downloads(self, pip_factory):
        pip, runner = pip_factory()
        pip.add_return((1, b"", b"SomeNetworkingError: Details here."))
        with pytest.raises(PackageDownloadError) as einfo:
            runner.download_all_dependencies("requirements.txt", "directory")
        assert str(einfo.value) == "SomeNetworkingError: Details here."

    def test_inject_unknown_error_if_no_stderr(self, pip_factory):
        pip, runner = pip_factory()
        pip.add_return((1, None, None))
        with pytest.raises(PackageDownloadError) as einfo:
            runner.download_all_dependencies("requirements.txt", "directory")
        assert str(einfo.value) == "Unknown error"


class TestSubprocessPip(TestCase):
    def test_does_use_custom_pip_import_string(self):
        fake_osutils = FakePopenOSUtils([FakePopen(0, "", "")])
        expected_import_statement = "foobarbaz"
        pip = SubprocessPip(osutils=fake_osutils, import_string=expected_import_statement, python_exe=sys.executable)
        pip.main(["--version"])

        pip_execution_string = fake_osutils.popens[0][0][0][2]
        import_statement = pip_execution_string.split(";")[1].strip()
        assert import_statement == expected_import_statement

    def test_check_pip_runner_string_pip(self):
        fake_osutils = FakePopenOSUtils([FakePopen(0, "", "")])
        pip = SubprocessPip(osutils=fake_osutils, python_exe=sys.executable)
        pip.main(["--version"])

        pip_runner_string = fake_osutils.popens[0][0][0][2].split(";")[-1:][0]
        self.assertIn("main", pip_runner_string)


class TestSDistMetadataFetcher(TestCase):
    @parameterized.expand(
        [
            (False,),
            (True,),
        ]
    )
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._unpack_sdist_into_dir")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_pkg_info_filepath")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_name_version")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_fallback_pkg_info_filepath")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._is_default_setuptools_values")
    @patch("aws_lambda_builders.workflows.python_pip.utils.OSUtils.file_exists")
    @patch("aws_lambda_builders.workflows.python_pip.utils.OSUtils.tempdir")
    def test_get_package_name_version_fails_fallback(
        self,
        fallback_file_exists,
        tempdir_mock,
        file_exists_mock,
        is_default_values_mock,
        get_fallback_mock,
        get_name_ver_mock,
        get_pkg_mock,
        unpack_mock,
    ):
        """
        Tests if both our generated PKG-INFO and PKG-INFO are missing/invalid
        """
        file_exists_mock.return_value = fallback_file_exists
        is_default_values_mock.return_value = True

        original_name = "UNKNOWN"
        original_version = "5.5.0"

        get_name_ver_mock.side_effect = [(original_name, original_version), ("UNKNOWN", "0.0.0")]

        sdist = SDistMetadataFetcher(OSUtils)
        name, version = sdist.get_package_name_and_version(mock.Mock())

        self.assertEqual(name, original_name)
        self.assertEqual(version, original_version)

    @parameterized.expand(
        [
            (("UNKNOWN", "1.2.3"),),
            (("unknown", "1.2.3"),),
            (("foobar", "0.0.0"),),
        ]
    )
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._unpack_sdist_into_dir")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_pkg_info_filepath")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_name_version")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_fallback_pkg_info_filepath")
    @patch("aws_lambda_builders.workflows.python_pip.utils.OSUtils.file_exists")
    @patch("aws_lambda_builders.workflows.python_pip.utils.OSUtils.tempdir")
    def test_get_package_name_version_fallback(
        self,
        name_version,
        tempdir_mock,
        file_exists_mock,
        get_fallback_mock,
        get_name_ver_mock,
        get_pkg_mock,
        unpack_mock,
    ):
        """
        Tests if we have UNKNOWN and if we use the fall back values
        """
        fallback_name = "fallback"
        fallback_version = "1.0.0"

        get_name_ver_mock.side_effect = [name_version, (fallback_name, fallback_version)]

        sdist = SDistMetadataFetcher(OSUtils)
        name, version = sdist.get_package_name_and_version(mock.Mock())

        self.assertEqual(name, fallback_name)
        self.assertEqual(version, fallback_version)

    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._unpack_sdist_into_dir")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_pkg_info_filepath")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_name_version")
    @patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher._get_fallback_pkg_info_filepath")
    @patch("aws_lambda_builders.workflows.python_pip.utils.OSUtils.file_exists")
    @patch("aws_lambda_builders.workflows.python_pip.utils.OSUtils.tempdir")
    def test_get_package_name_version(
        self,
        tempdir_mock,
        file_exists_mock,
        get_fallback_mock,
        get_name_ver_mock,
        get_pkg_mock,
        unpack_mock,
    ):
        """
        Tests return original results
        """
        not_default_name = "real"
        not_default_version = "1.2.3"

        fallback_name = "fallback"
        fallback_version = "1.0.0"

        get_name_ver_mock.side_effect = [(not_default_name, not_default_version), (fallback_name, fallback_version)]

        sdist = SDistMetadataFetcher(OSUtils)
        name, version = sdist.get_package_name_and_version(mock.Mock())

        self.assertEqual(name, not_default_name)
        self.assertEqual(version, not_default_version)


class TestDependencyBuilder(object):
    def test_has_at_least_one_package_file_not_exists(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.file_exists.return_value = False
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        result = builder._has_at_least_one_package("nonexistent.txt")
        assert result is False

    def test_has_at_least_one_package_empty_file(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.file_exists.return_value = True
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        with mock.patch("builtins.open", mock.mock_open(read_data="")):
            result = builder._has_at_least_one_package("empty.txt")
        assert result is False

    def test_has_at_least_one_package_only_comments(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.file_exists.return_value = True
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        with mock.patch("builtins.open", mock.mock_open(read_data="# comment\n  # another comment\n")):
            result = builder._has_at_least_one_package("comments.txt")
        assert result is False

    def test_has_at_least_one_package_with_packages(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.file_exists.return_value = True
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        with mock.patch("builtins.open", mock.mock_open(read_data="# comment\nrequests==2.25.1\n")):
            result = builder._has_at_least_one_package("requirements.txt")
        assert result is True

    def test_build_site_packages_no_packages(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.file_exists.return_value = False
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Should not raise any exception and not call other methods
        builder.build_site_packages("empty.txt", "target", "scratch")

    def test_build_site_packages_with_missing_dependencies(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.file_exists.return_value = True
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Mock _has_at_least_one_package to return True
        builder._has_at_least_one_package = mock.Mock(return_value=True)

        # Mock _download_dependencies to return empty wheels and some missing packages
        missing_packages = [mock.Mock()]
        builder._download_dependencies = mock.Mock(return_value=(set(), missing_packages))
        builder._install_wheels = mock.Mock()

        with mock.patch("builtins.open", mock.mock_open(read_data="requests==2.25.1\n")):
            with pytest.raises(MissingDependencyError) as exc_info:
                builder.build_site_packages("requirements.txt", "target", "scratch")

        assert exc_info.value.missing == missing_packages

    def test_compatible_platforms_x86_64_python38(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner, architecture=X86_64)

        platforms = builder.compatible_platforms
        expected = [
            "any",
            "linux_x86_64",
            "manylinux1_x86_64",
            "manylinux2010_x86_64",
            "manylinux2014_x86_64",
            "manylinux_2_17_x86_64",
        ]
        assert platforms == expected

    def test_compatible_platforms_arm64_python312(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.12", sys.executable, pip_runner, architecture=ARM64)

        platforms = builder.compatible_platforms
        expected = [
            "any",
            "linux_aarch64",
            "manylinux2014_aarch64",
            "manylinux_2_17_aarch64",
            "manylinux_2_28_aarch64",
            "manylinux_2_34_aarch64",
        ]
        assert platforms == expected

    def test_is_compatible_wheel_filename_pure_python(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Pure python wheel
        result = builder._is_compatible_wheel_filename("package-1.0-py3-none-any.whl")
        assert result is True

    def test_is_compatible_wheel_filename_compatible_platform(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Compatible platform wheel
        result = builder._is_compatible_wheel_filename("package-1.0-cp38-cp38-linux_x86_64.whl")
        assert result is True

    def test_is_compatible_wheel_filename_incompatible(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Incompatible wheel
        result = builder._is_compatible_wheel_filename("package-1.0-cp39-cp39-win_amd64.whl")
        assert result is False

    def test_is_compatible_platform_tag_legacy_manylinux(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Test legacy manylinux tag
        result = builder._is_compatible_platform_tag("cp38", "manylinux1_x86_64")
        assert result is True

    def test_is_compatible_platform_tag_newer_glibc(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Test newer glibc version (should be incompatible)
        result = builder._is_compatible_platform_tag("cp38", "manylinux_2_35_x86_64")
        assert result is False

    def test_is_compatible_platform_tag_invalid_format(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Test invalid platform tag format
        result = builder._is_compatible_platform_tag("cp38", "invalid_platform")
        assert result is False

    def test_iter_all_compatibility_tags(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        wheel = "numpy-1.20.3-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64"
        tags = list(builder._iter_all_compatibility_tags(wheel))

        expected_tags = [("cp38", "cp38", "manylinux_2_17_x86_64"), ("cp38", "cp38", "manylinux2014_x86_64")]
        assert tags == expected_tags

    def test_apply_wheel_allowlist(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Create mock packages
        compatible_pkg = mock.Mock()
        compatible_pkg.name = "compatible"

        allowlisted_pkg = mock.Mock()
        allowlisted_pkg.name = "sqlalchemy"  # This is in the allowlist

        incompatible_pkg = mock.Mock()
        incompatible_pkg.name = "incompatible"

        compatible_wheels = {compatible_pkg}
        incompatible_wheels = {allowlisted_pkg, incompatible_pkg}

        result_compatible, result_incompatible = builder._apply_wheel_allowlist(compatible_wheels, incompatible_wheels)

        assert allowlisted_pkg in result_compatible
        assert compatible_pkg in result_compatible
        assert incompatible_pkg in result_incompatible
        assert allowlisted_pkg not in result_incompatible

    def test_install_purelib_and_platlib_no_data_dir(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.directory_exists.return_value = False
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        wheel = mock.Mock()
        wheel.data_dir = "package-1.0.data"

        # Should not raise any exception
        builder._install_purelib_and_platlib(wheel, "/root")
        osutils.directory_exists.assert_called_once()

    def test_install_purelib_and_platlib_with_dirs(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.directory_exists.return_value = True
        osutils.get_directory_contents.return_value = ["purelib", "platlib", "other"]
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        wheel = mock.Mock()
        wheel.data_dir = "package-1.0.data"

        builder._install_purelib_and_platlib(wheel, "/root")

        # Should copy purelib and platlib directories
        assert osutils.copytree.call_count == 2
        assert osutils.rmtree.call_count == 2

    def test_install_wheels(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.directory_exists.return_value = True
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        wheel1 = mock.Mock()
        wheel1.filename = "package1-1.0-py3-none-any.whl"
        wheel2 = mock.Mock()
        wheel2.filename = "package2-2.0-py3-none-any.whl"

        wheels = [wheel1, wheel2]

        builder._install_purelib_and_platlib = mock.Mock()

        builder._install_wheels("/src", "/dst", wheels)

        osutils.rmtree.assert_called_once_with("/dst")
        osutils.makedirs.assert_called_once_with("/dst")
        assert osutils.extract_zipfile.call_count == 2
        assert builder._install_purelib_and_platlib.call_count == 2


class TestSDistMetadataFetcherAdditional(TestCase):
    def test_get_pkg_info_filepath_setuptools_not_available(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        osutils.makedirs = mock.Mock()
        osutils.get_directory_contents.return_value = []
        osutils.file_exists.return_value = False
        osutils.basename.return_value = "test-package"

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1  # Simulate setuptools not available

            with mock.patch("subprocess.Popen") as mock_popen:
                mock_process = mock.Mock()
                mock_process.returncode = 1
                mock_process.communicate.return_value = (b"", b"setuptools not found")
                mock_popen.return_value = mock_process

                with pytest.raises(UnsupportedPackageError):
                    fetcher._get_pkg_info_filepath("/package/dir")

    def test_get_pkg_info_filepath_with_existing_egg_info(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        osutils.makedirs = mock.Mock()
        osutils.get_directory_contents.side_effect = [
            [],  # First call for egg-info dir (empty)
            ["existing.egg-info", "other-file"],  # Second call for package contents
        ]
        osutils.file_exists.side_effect = lambda path: path == "/package/dir/existing.egg-info/PKG-INFO"
        osutils.directory_exists.side_effect = lambda path: path == "/package/dir/existing.egg-info"

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        with mock.patch("subprocess.Popen") as mock_popen:
            mock_process = mock.Mock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b"", b"some error")
            mock_popen.return_value = mock_process

            result = fetcher._get_pkg_info_filepath("/package/dir")
            assert result == "/package/dir/existing.egg-info/PKG-INFO"

    def test_get_fallback_pkg_info_filepath(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)
        result = fetcher._get_fallback_pkg_info_filepath("/package/dir")

        assert result == "/package/dir/PKG-INFO"

    def test_unpack_sdist_into_dir_zip(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.extract_zipfile = mock.Mock()
        osutils.get_directory_contents.return_value = ["extracted-dir"]
        osutils.joinpath.side_effect = lambda *args: "/".join(args)

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)
        result = fetcher._unpack_sdist_into_dir("/path/to/package.zip", "/unpack/dir")

        osutils.extract_zipfile.assert_called_once_with("/path/to/package.zip", "/unpack/dir")
        assert result == "/unpack/dir/extracted-dir"

    def test_unpack_sdist_into_dir_tar_gz(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.get_directory_contents.return_value = ["extracted-dir"]
        osutils.joinpath.side_effect = lambda *args: "/".join(args)

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.extract_tarfile") as mock_extract:
            result = fetcher._unpack_sdist_into_dir("/path/to/package.tar.gz", "/unpack/dir")

            mock_extract.assert_called_once_with("/path/to/package.tar.gz", "/unpack/dir")
            assert result == "/unpack/dir/extracted-dir"

    def test_unpack_sdist_into_dir_tar_bz2(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.get_directory_contents.return_value = ["extracted-dir"]
        osutils.joinpath.side_effect = lambda *args: "/".join(args)

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.extract_tarfile") as mock_extract:
            result = fetcher._unpack_sdist_into_dir("/path/to/package.tar.bz2", "/unpack/dir")

            mock_extract.assert_called_once_with("/path/to/package.tar.bz2", "/unpack/dir")
            assert result == "/unpack/dir/extracted-dir"

    def test_unpack_sdist_into_dir_invalid_extension(self):
        osutils = mock.Mock(spec=OSUtils)
        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        with pytest.raises(InvalidSourceDistributionNameError):
            fetcher._unpack_sdist_into_dir("/path/to/package.invalid", "/unpack/dir")

    def test_get_name_version(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.get_file_contents.return_value = "Name: test-package\nVersion: 1.0.0\n"

        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)
        name, version = fetcher._get_name_version("/path/to/PKG-INFO")

        assert name == "test-package"
        assert version == "1.0.0"

    def test_is_default_setuptools_values_unknown_name(self):
        osutils = mock.Mock(spec=OSUtils)
        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        assert fetcher._is_default_setuptools_values("UNKNOWN", "1.0.0") is True
        assert fetcher._is_default_setuptools_values("unknown", "1.0.0") is True

    def test_is_default_setuptools_values_default_version(self):
        osutils = mock.Mock(spec=OSUtils)
        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        assert fetcher._is_default_setuptools_values("package", "0.0.0") is True

    def test_is_default_setuptools_values_valid(self):
        osutils = mock.Mock(spec=OSUtils)
        fetcher = SDistMetadataFetcher(sys.executable, osutils=osutils)

        assert fetcher._is_default_setuptools_values("package", "1.0.0") is False


class TestPackageAdditional(object):
    def test_package_sdist_with_metadata_fetcher(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)

        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.SDistMetadataFetcher") as mock_fetcher_class:
            mock_fetcher = mock.Mock()
            mock_fetcher.get_package_name_and_version.return_value = ("test-package", "1.0.0")
            mock_fetcher_class.return_value = mock_fetcher

            pkg = Package("/dir", "test-package-1.0.tar.gz", sys.executable, osutils)

            assert pkg.dist_type == "sdist"
            assert pkg.name == "test-package"
            assert pkg.identifier == "test-package==1.0.0"

    def test_package_normalize_name_with_underscores_and_dots(self):
        pkg = Package("", "test_package.name-1.0-py3-none-any.whl", sys.executable)
        assert pkg.name == "test-package-name"


class TestPythonPipDependencyBuilderAdditional(object):
    def test_default_osutils_creation(self):
        # Test the case where osutils is None and gets created
        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.DependencyBuilder") as mock_dep_builder:
            builder = PythonPipDependencyBuilder(runtime="python3.8", python_exe=sys.executable)
            assert builder.osutils is not None
            assert isinstance(builder.osutils, OSUtils)

    def test_default_dependency_builder_creation(self):
        # Test the case where dependency_builder is None and gets created
        osutils_mock = mock.Mock(spec=OSUtils)
        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.DependencyBuilder") as mock_dep_builder:
            builder = PythonPipDependencyBuilder(runtime="python3.8", python_exe=sys.executable, osutils=osutils_mock)
            mock_dep_builder.assert_called_once_with(osutils_mock, sys.executable, "python3.8", architecture=X86_64)


class TestDependencyBuilderAdditional(object):
    def test_default_pip_runner_creation(self):
        # Test the case where pip_runner is None and gets created
        osutils = mock.Mock(spec=OSUtils)
        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.PipRunner") as mock_pip_runner:
            with mock.patch("aws_lambda_builders.workflows.python_pip.packager.SubprocessPip") as mock_subprocess_pip:
                builder = DependencyBuilder(osutils, "python3.8", sys.executable)
                mock_subprocess_pip.assert_called_once_with(osutils)
                mock_pip_runner.assert_called_once()

    def test_categorize_wheel_files(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.get_directory_contents.return_value = [
            "compatible-1.0-py3-none-any.whl",
            "incompatible-1.0-cp39-cp39-win_amd64.whl",
            "not-a-wheel.tar.gz",
        ]
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.Package") as mock_package:
            # Mock Package instances
            compatible_pkg = mock.Mock()
            compatible_pkg.filename = "compatible-1.0-py3-none-any.whl"
            incompatible_pkg = mock.Mock()
            incompatible_pkg.filename = "incompatible-1.0-cp39-cp39-win_amd64.whl"

            mock_package.side_effect = [compatible_pkg, incompatible_pkg]

            # Mock the wheel filename compatibility check
            builder._is_compatible_wheel_filename = mock.Mock(side_effect=[True, False])

            compatible, incompatible = builder._categorize_wheel_files("/test/dir")

            assert compatible_pkg in compatible
            assert incompatible_pkg in incompatible

    def test_build_sdists(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.joinpath.side_effect = lambda *args: "/".join(args)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Create mock sdist packages
        sdist1 = mock.Mock()
        sdist1.filename = "package1-1.0.tar.gz"
        sdist2 = mock.Mock()
        sdist2.filename = "package2-2.0.tar.gz"

        sdists = {sdist1, sdist2}

        builder._build_sdists(sdists, "/test/dir", compile_c=True)

        # Should call build_wheel for each sdist
        assert pip_runner.build_wheel.call_count == 2
        pip_runner.build_wheel.assert_any_call("/test/dir/package1-1.0.tar.gz", "/test/dir", True)
        pip_runner.build_wheel.assert_any_call("/test/dir/package2-2.0.tar.gz", "/test/dir", True)

    def test_download_binary_wheels(self):
        osutils = mock.Mock(spec=OSUtils)
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        # Create mock packages
        pkg1 = mock.Mock()
        pkg1.identifier = "package1==1.0"
        pkg2 = mock.Mock()
        pkg2.identifier = "package2==2.0"

        packages = {pkg1, pkg2}

        builder._download_binary_wheels(packages, "/test/dir")

        # Check that download_manylinux_wheels was called with the right parameters
        # Note: set order is not guaranteed, so we check the call was made with the right args
        call_args = pip_runner.download_manylinux_wheels.call_args
        assert call_args is not None
        identifiers, directory, abi, platforms = call_args[0]
        assert set(identifiers) == {"package1==1.0", "package2==2.0"}
        assert directory == "/test/dir"
        assert abi == "cp38"
        assert platforms == builder.compatible_platforms

    def test_download_all_dependencies(self):
        osutils = mock.Mock(spec=OSUtils)
        osutils.get_directory_contents.return_value = ["package1-1.0.tar.gz", "package2-2.0-py3-none-any.whl"]
        pip_runner = mock.Mock(spec=PipRunner)
        builder = DependencyBuilder(osutils, "python3.8", sys.executable, pip_runner)

        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.Package") as mock_package:
            # Mock Package instances
            pkg1 = mock.Mock()
            pkg2 = mock.Mock()
            mock_package.side_effect = [pkg1, pkg2]

            result = builder._download_all_dependencies("/requirements.txt", "/test/dir")

            pip_runner.download_all_dependencies.assert_called_once_with("/requirements.txt", "/test/dir")
            assert pkg1 in result
            assert pkg2 in result


class TestPackageEdgeCases(object):
    def test_package_invalid_sdist_extension(self):
        with pytest.raises(InvalidSourceDistributionNameError):
            Package("", "invalid-package.unknown", sys.executable)

    def test_package_data_dir_property(self):
        pkg = Package("", "test_package-1.2.3-py3-none-any.whl", sys.executable)
        # The data_dir uses the normalized name and version
        assert pkg.data_dir == "test-package-1.2.3.data"


class TestSubprocessPipEdgeCases(object):
    def test_subprocess_pip_with_custom_python_exe(self):
        osutils = mock.Mock(spec=OSUtils)
        with mock.patch("aws_lambda_builders.workflows.python_pip.packager.pip_import_string") as mock_import:
            mock_import.return_value = "import pip"
            pip = SubprocessPip(osutils=osutils, python_exe="/custom/python")
            assert pip.python_exe == "/custom/python"

    def test_subprocess_pip_main_with_custom_env_and_shim(self):
        fake_osutils = FakePopenOSUtils([FakePopen(0, b"output", b"error")])
        pip = SubprocessPip(osutils=fake_osutils, python_exe=sys.executable)

        custom_env = {"CUSTOM_VAR": "value"}
        custom_shim = "custom_shim_code;"

        rc, out, err = pip.main(["--version"], env_vars=custom_env, shim=custom_shim)

        assert rc == 0
        assert out == b"output"
        assert err == b"error"

        # Check that custom env and shim were used
        call_args, call_kwargs = fake_osutils.popens[0]
        assert call_kwargs["env"] == custom_env
        exec_string = call_args[0][2]
        assert exec_string.startswith(custom_shim)
