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
