from unittest import TestCase
from mock import patch
from parameterized import parameterized

from aws_lambda_builders.workflows.nodejs_npm.npm import SubprocessNpm, NpmExecutionError, NpmModulesUtils


class FakePopen:
    def __init__(self, out=b'out', err=b'err', retcode=0):
        self.out = out
        self.err = err
        self.returncode = retcode

    def communicate(self):
        return self.out, self.err


class TestSubprocessNpm(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def setUp(self, OSUtilMock):

        self.osutils = OSUtilMock.return_value
        self.osutils.pipe = 'PIPE'
        self.popen = FakePopen()
        self.osutils.popen.side_effect = [self.popen]
        self.under_test = SubprocessNpm(self.osutils, npm_exe="/a/b/c/npm.exe")

    def test_run_executes_npm_on_nixes(self):

        self.osutils.is_windows.side_effect = [False]

        self.under_test = SubprocessNpm(self.osutils)

        self.under_test.run(['pack', '-q'])

        self.osutils.popen.assert_called_with(['npm', 'pack', '-q'], cwd=None, stderr='PIPE', stdout='PIPE')

    def test_run_executes_npm_cmd_on_windows(self):

        self.osutils.is_windows.side_effect = [True]

        self.under_test = SubprocessNpm(self.osutils)

        self.under_test.run(['pack', '-q'])

        self.osutils.popen.assert_called_with(['npm.cmd', 'pack', '-q'], cwd=None, stderr='PIPE', stdout='PIPE')

    def test_uses_custom_npm_path_if_supplied(self):

        self.under_test.run(['pack', '-q'])

        self.osutils.popen.assert_called_with(['/a/b/c/npm.exe', 'pack', '-q'], cwd=None, stderr='PIPE', stdout='PIPE')

    def test_uses_cwd_if_supplied(self):

        self.under_test.run(['pack', '-q'], cwd='/a/cwd')

        self.osutils.popen.assert_called_with(['/a/b/c/npm.exe', 'pack', '-q'],
                                              cwd='/a/cwd', stderr='PIPE', stdout='PIPE')

    def test_returns_popen_out_decoded_if_retcode_is_0(self):

        self.popen.out = b'some encoded text\n\n'

        result = self.under_test.run(['pack'])

        self.assertEqual(result, 'some encoded text')

    def test_raises_NpmExecutionError_with_err_text_if_retcode_is_not_0(self):

        self.popen.returncode = 1
        self.popen.err = b'some error text\n\n'

        with self.assertRaises(NpmExecutionError) as raised:
            self.under_test.run(['pack'])

        self.assertEqual(raised.exception.args[0], "NPM Failed: some error text")

    def test_raises_ValueError_if_args_not_a_list(self):

        with self.assertRaises(ValueError) as raised:
            self.under_test.run(('pack'))

        self.assertEqual(raised.exception.args[0], "args must be a list")

    def test_raises_ValueError_if_args_empty(self):

        with self.assertRaises(ValueError) as raised:
            self.under_test.run([])

        self.assertEqual(raised.exception.args[0], "requires at least one arg")


class TestNpmModulesUtils(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def setUp(self, OSUtilMock, SubprocessNpmMock):

        self.osutils = OSUtilMock.return_value
        self.subprocess_npm = SubprocessNpmMock.return_value
        self.under_test = NpmModulesUtils(self.osutils, self.subprocess_npm, 'scratch_dir')
        self.osutils.joinpath.side_effect = lambda a, b, c='': a + '/' + b + '/' + c if c else a + '/' + b
        self.osutils.abspath.side_effect = lambda a: '/absolute/' + a
        self.osutils.tempdir.side_effect = lambda a: a + '/tempdir'

    def test_get_local_dependencies_reads_package_json(self):
        self.osutils.get_text_contents.side_effect = ['{}']
        self.osutils.joinpath.side_effect = ['joined/path']

        self.under_test.get_local_dependencies('some/dir')

        self.osutils.get_text_contents.assert_called_with('joined/path')
        self.osutils.joinpath.assert_called_with('some/dir', 'package.json')

    def test_get_local_dependencies_returns_empty_dict_when_no_dependencies(self):
        self.osutils.get_text_contents.side_effect = ['{}']

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {})

    def test_get_local_dependencies_returns_empty_dict_whitout_local_dependencies(self):
        self.osutils.get_text_contents.side_effect = ['{"dependencies":{"claudia":"*"}}']

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {})

    def test_get_local_dependencies_return_dict_with_local_dependencies(self):
        self.osutils.get_text_contents.side_effect = ['{"dependencies":{"claudia":"file:/claudia/"}}']

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {'claudia': 'file:/claudia/'})

    def test_get_local_dependencies_filters_only_local_dependencies(self):
        self.osutils.get_text_contents.side_effect = [
            '{"dependencies":{"claudia":"*","aws-sdk":"*","foo":"file:/foo","bar":"./bar","baz":"/baz"}}'
        ]

        result = self.under_test.get_local_dependencies('some/dir')

        self.assertEqual(result, {'foo': 'file:/foo', 'bar': './bar', 'baz': '/baz'})

    def test_get_local_dependencies_from_a_defined_key(self):
        self.osutils.get_text_contents.side_effect = ['{"optionalDependencies":{"claudia":"file:/claudia/"}}']

        result = self.under_test.get_local_dependencies('some/dir', 'optionalDependencies')

        self.assertEqual(result, {'claudia': 'file:/claudia/'})

    @parameterized.expand([
        # NPM Version numbers and ranges from https://docs.npmjs.com/files/package.json
        "1.0.0 - 2.9999.9999",
        ">=1.0.2 <2.1.2",
        "<1.0.2",
        "<=1.0.2",
        ">1.0.2 <=2.3.4",
        "2.0.1",
        "<1.0.0 || >=2.3.1 <2.4.5 || >=2.5.2 <3.0.0",
        "~1.2",
        "~1.2.3",
        "2.x",
        "3.3.x",
        "latest",
        "*",
        # URLs as Dependencies
        "http://asdf.com/asdf.tar.gz",
        # Git URLs as Dependencies
        "git+ssh://git@github.com:npm/cli.git#v1.0.27"
        "git+ssh://git@github.com:npm/cli#semver:^5.0"
        "git+https://isaacs@github.com/npm/cli.git"
        "git://github.com/npm/cli.git#v1.0.27"
        # GitHub URLs
        "expressjs/express",
        "mochajs/mocha#4727d357ea",
        "user/repo#feature\/branch"
    ])
    def test_is_local_dependency_returns_false_for_remote_dependencies(self, dependency_ref):
        print('using', dependency_ref)
        self.assertFalse(self.under_test.is_local_dependency(dependency_ref))

    @parameterized.expand([
        "../foo/bar",
        "~/foo/bar",
        "./foo/bar",
        "/foo/bar",
        "file:../foo/bar"
    ])
    def test_is_local_dependency_returns_true_for_local_dependencies(self, dependency_ref):
        self.assertTrue(self.under_test.is_local_dependency(dependency_ref))

    def test_has_local_dependencies_returns_false_if_no_dependencies(self):
        self.osutils.get_text_contents.side_effect = lambda path: '{"name":"test-project"}'

        self.assertFalse(self.under_test.has_local_dependencies('project_path'))
        self.osutils.get_text_contents.assert_called_with('project_path/package.json')

    @parameterized.expand([
        '{"optionalDependencies":{"claudia":"1.0.0"}}',
        '{"dependencies":{"claudia":"1.0.0"}}',
        '{"dependencies":{"claudia":"1.0.0"}, "optionalDependencies":{"express":"*"}}',
    ])
    def test_has_local_dependencies_returns_false_if_only_remote_dependencies(self, package_manifest):
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest

        self.assertFalse(self.under_test.has_local_dependencies('project_path'))

    def test_has_local_dependencies_ignores_development_dependencies(self):
        package_manifest = '{"devDependencies":{"claudia":"file:../claudia"}}'
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest

        self.assertFalse(self.under_test.has_local_dependencies('project_path'))

    @parameterized.expand([
        '{"optionalDependencies":{"claudia":"file:../local"}}',
        '{"optionalDependencies":{"express": "*", "claudia":"file:../local"}}',
        '{"dependencies":{"claudia":"file:../local"}}',
        '{"dependencies":{"express": "*", "claudia":"file:../local"}}',
        '{"dependencies":{"claudia":"file:../local"}, "optionalDependencies":{"express":"*"}}',
        '{"dependencies":{"claudia":"*"}, "optionalDependencies":{"express":"file:../local"}}',
    ])
    def test_has_local_dependencies_returns_false_if_some_local_dependencies(self, package_manifest):
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest

        self.assertTrue(self.under_test.has_local_dependencies('project_path'))

    def test_pack_to_tar_uses_subprocess_npm_to_execute_npm_pack(self):
        self.subprocess_npm.run.side_effect = ['archive.tar']
        result = self.under_test.pack_to_tar('package_dir')
        self.assertEquals(result, 'scratch_dir/archive.tar')
        self.subprocess_npm.run.assert_called_with(['pack', '-q', 'file:/absolute/package_dir'], cwd='scratch_dir')

    def test_update_dependency_rewrites_production_dependencies_without_specific_dependency_key(self):
        package_manifest = '{"dependencies":{"claudia":"file:../claudia"}}'
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest
        self.under_test.update_dependency('package_dir', 'claudia', 'file:/a.tar')
        self.osutils.get_text_contents.assert_called_with('package_dir/package.json')
        self.osutils.write_text_contents.assert_called_with(
            'package_dir/package.json',
            '{"dependencies": {"claudia": "file:/a.tar"}}'
        )

    def test_update_dependency_rewrites_production_dependencies_does_not_modify_other_dependencies(self):
        package_manifest = '{"dependencies":{"claudia":"file:../claudia", "express": "*"}}'
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest
        self.under_test.update_dependency('package_dir', 'claudia', 'file:/a.tar')
        self.osutils.get_text_contents.assert_called_with('package_dir/package.json')
        self.osutils.write_text_contents.assert_called_with(
            'package_dir/package.json',
            '{"dependencies": {"claudia": "file:/a.tar", "express": "*"}}'
        )

    def test_update_dependency_rewrites_production_dependencies_with_specific_dependency_key(self):
        package_manifest = '{"dependencies":{"claudia":"file:../claudia"}}'
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest
        self.under_test.update_dependency('package_dir', 'claudia', 'file:/a.tar', 'dependencies')
        self.osutils.get_text_contents.assert_called_with('package_dir/package.json')
        self.osutils.write_text_contents.assert_called_with(
            'package_dir/package.json',
            '{"dependencies": {"claudia": "file:/a.tar"}}'
        )

    def test_update_dependency_rewrites_optional_dependencies_if_requested(self):
        package_manifest = '{"optionalDependencies":{"claudia":"file:../claudia"}}'
        self.osutils.get_text_contents.side_effect = lambda path: package_manifest
        self.under_test.update_dependency('package_dir', 'claudia', 'file:/a.tar', 'optionalDependencies')
        self.osutils.get_text_contents.assert_called_with('package_dir/package.json')
        self.osutils.write_text_contents.assert_called_with(
            'package_dir/package.json',
            '{"optionalDependencies": {"claudia": "file:/a.tar"}}'
        )

    def test_clean_copy_packs_a_project_to_tar_and_extracts_from_tar_into_temp_dir(self):
        self.subprocess_npm.run.side_effect = ['archive.tar']

        result = self.under_test.clean_copy('project_dir')

        self.assertEquals(result, 'scratch_dir/tempdir/package')
        self.subprocess_npm.run.assert_called_with(['pack', '-q', 'file:/absolute/project_dir'], cwd='scratch_dir')
        self.osutils.extract_tarfile.assert_called_with('scratch_dir/archive.tar', 'scratch_dir/tempdir')

    def test_clean_copy_removes_package_lock_if_requested_and_exists(self):
        self.subprocess_npm.run.side_effect = ['archive.tar']
        self.osutils.file_exists.side_effect = [True]

        result = self.under_test.clean_copy('project_dir', True)

        self.assertEquals(result, 'scratch_dir/tempdir/package')
        self.osutils.file_exists.assert_called_with('scratch_dir/tempdir/package/package-lock.json')
        self.osutils.remove_file.assert_called_with('scratch_dir/tempdir/package/package-lock.json')

    def test_clean_copy_does_not_removes_package_lock_if_it_does_not_exist_even_if_requested(self):
        self.subprocess_npm.run.side_effect = ['archive.tar']
        self.osutils.file_exists.side_effect = [False]

        result = self.under_test.clean_copy('project_dir', True)

        self.assertEquals(result, 'scratch_dir/tempdir/package')
        self.osutils.file_exists.assert_called_with('scratch_dir/tempdir/package/package-lock.json')
        self.osutils.remove_file.assert_not_called()
