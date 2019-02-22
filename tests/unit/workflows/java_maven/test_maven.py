import subprocess

from unittest import TestCase
from mock import patch

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.workflows.java_maven.maven import SubprocessMaven, MavenExecutionError


class FakePopen:
    def __init__(self, out=b'out', err=b'err', retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err

    def wait(self):
        pass


class TestSubprocessMaven(TestCase):

    @patch("aws_lambda_builders.workflows.java_gradle.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value
        self.os_utils.exists.side_effect = lambda d: True
        self.popen = FakePopen()
        self.os_utils.popen.side_effect = [self.popen]
        self.maven_path = '/path/to/mvn'
        self.maven_binary = BinaryPath(None, None, 'maven', binary_path=self.maven_path)
        self.source_dir = '/foo/bar/helloworld'
        self.root_dir = '/foo/bar'
        self.module_name = 'helloworld'
        # self.manifest_path = '/foo/bar/baz/build.maven'

    def test_no_os_utils_build_init_throws(self):
        with self.assertRaises(ValueError) as err_assert:
            SubprocessMaven(maven_binary=self.maven_binary)
        self.assertEquals(err_assert.exception.args[0], 'Must provide OSUtils')

    def test_no_maven_exec_init_throws(self):
        with self.assertRaises(ValueError) as err_assert:
            SubprocessMaven(None)
        self.assertEquals(err_assert.exception.args[0], 'Must provide Maven BinaryPath')

    def test_build_single_project(self):
        maven = SubprocessMaven(maven_binary=self.maven_binary, os_utils=self.os_utils)
        maven.build(self.source_dir)
        self.os_utils.popen.assert_called_with(
            [self.maven_path, 'clean', 'package'],
            cwd=self.source_dir, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    def test_build_multimodule_project(self):
        maven = SubprocessMaven(maven_binary=self.maven_binary, os_utils=self.os_utils)
        maven.build(self.source_dir, self.module_name, self.root_dir)
        self.os_utils.popen.assert_called_with(
            [self.maven_path, 'clean', 'install', '-pl', self.module_name, '--also-make'],
            cwd=self.root_dir, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    def test_build_raises_exception_if_retcode_not_0(self):
        self.popen = FakePopen(retcode=1, err=b'Some Error Message')
        self.os_utils.popen.side_effect = [self.popen]
        maven = SubprocessMaven(maven_binary=self.maven_binary, os_utils=self.os_utils)
        with self.assertRaises(MavenExecutionError) as err:
            maven.build(self.source_dir)
        self.assertEquals(err.exception.args[0], 'Maven Failed: Some Error Message')

    def test_copy_dependency_single_project(self):
        maven = SubprocessMaven(maven_binary=self.maven_binary, os_utils=self.os_utils)
        maven.copy_dependency(self.source_dir)
        self.os_utils.popen.assert_called_with(
            [self.maven_path, 'dependency:copy-dependencies', '-DincludeScope=compile'],
            cwd=self.source_dir, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    def test_copy_dependency_multimodule_project(self):
        maven = SubprocessMaven(maven_binary=self.maven_binary, os_utils=self.os_utils)
        maven.copy_dependency(self.source_dir, self.module_name, self.root_dir)
        self.os_utils.popen.assert_called_with(
            [self.maven_path, 'dependency:copy-dependencies', '-DincludeScope=compile', '-pl', self.module_name],
            cwd=self.root_dir, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    def test_copy_dependency_raises_exception_if_retcode_not_0(self):
        self.popen = FakePopen(retcode=1, err=b'Some Error Message')
        self.os_utils.popen.side_effect = [self.popen]
        maven = SubprocessMaven(maven_binary=self.maven_binary, os_utils=self.os_utils)
        with self.assertRaises(MavenExecutionError) as err:
            maven.copy_dependency(self.source_dir)
        self.assertEquals(err.exception.args[0], 'Maven Failed: Some Error Message')
