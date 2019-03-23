from unittest import TestCase
from mock import patch, call

from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.workflows.nodejs_npm.actions import \
    NodejsNpmPackAction, NodejsNpmInstallAction, NodejsNpmrcCopyAction, \
    NodejsNpmrcCleanUpAction, NodejsNpmRewriteLocalDependenciesAction
from aws_lambda_builders.workflows.nodejs_npm.npm import NpmExecutionError


class TestNodejsNpmPackAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmPackAction("artifacts", "scratch_dir",
                                     "manifest",
                                     osutils=osutils,
                                     subprocess_npm=subprocess_npm)

        osutils.dirname.side_effect = lambda value: "/dir:{}".format(value)
        osutils.abspath.side_effect = lambda value: "/abs:{}".format(value)
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        subprocess_npm.run.return_value = 'package.tar'

        action.execute()

        subprocess_npm.run.assert_called_with(['pack', '-q', 'file:/abs:/dir:manifest'], cwd='scratch_dir')
        osutils.extract_tarfile.assert_called_with('scratch_dir/package.tar', 'artifacts')

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, OSUtilMock, SubprocessNpmMock):
        osutils = OSUtilMock.return_value
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmPackAction("artifacts", "scratch_dir",
                                     "manifest",
                                     osutils=osutils, subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmInstallAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_tars_and_unpacks_npm_project(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        action = NodejsNpmInstallAction("artifacts",
                                        subprocess_npm=subprocess_npm)

        action.execute()

        expected_args = ['install', '-q', '--no-audit', '--no-save', '--production']

        subprocess_npm.run.assert_called_with(expected_args, cwd='artifacts')

    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm")
    def test_raises_action_failed_when_npm_fails(self, SubprocessNpmMock):
        subprocess_npm = SubprocessNpmMock.return_value

        builder_instance = SubprocessNpmMock.return_value
        builder_instance.run.side_effect = NpmExecutionError(message="boom!")

        action = NodejsNpmInstallAction("artifacts",
                                        subprocess_npm=subprocess_npm)

        with self.assertRaises(ActionFailedError) as raised:
            action.execute()

        self.assertEqual(raised.exception.args[0], "NPM Failed: boom!")


class TestNodejsNpmrcCopyAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_copies_npmrc_into_a_project(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCopyAction("artifacts",
                                       "source",
                                       osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.file_exists.assert_called_with("source/.npmrc")
        osutils.copy_file.assert_called_with("source/.npmrc", "artifacts")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_copying_npmrc_into_a_project_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCopyAction("artifacts",
                                       "source",
                                       osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.file_exists.assert_called_with("source/.npmrc")
        osutils.copy_file.assert_not_called()

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_raises_action_failed_when_copying_fails(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        osutils.copy_file.side_effect = OSError()

        action = NodejsNpmrcCopyAction("artifacts",
                                       "source",
                                       osutils=osutils)

        with self.assertRaises(ActionFailedError):
            action.execute()


class TestNodejsNpmrcCleanUpAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_removes_npmrc_if_npmrc_exists(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction(
                                     "artifacts",
                                     osutils=osutils)
        osutils.file_exists.side_effect = [True]
        action.execute()

        osutils.remove_file.assert_called_with("artifacts/.npmrc")

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    def test_skips_npmrc_removal_if_npmrc_doesnt_exist(self, OSUtilMock):
        osutils = OSUtilMock.return_value
        osutils.joinpath.side_effect = lambda a, b: "{}/{}".format(a, b)

        action = NodejsNpmrcCleanUpAction(
                                     "artifacts",
                                     osutils=osutils)
        osutils.file_exists.side_effect = [False]
        action.execute()

        osutils.remove_file.assert_not_called()


class TestNodejsNpmRewriteLocalDependenciesAction(TestCase):

    @patch("aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils")
    @patch("aws_lambda_builders.workflows.nodejs_npm.npm.NpmModulesUtils")
    def setUp(self, OSUtilMock, NpmModulesUtils):
        self.osutils = OSUtilMock.return_value
        self.osutils.joinpath.side_effect = \
            lambda original_package_dir, module_path: original_package_dir + '/' + module_path

        self.npm_modules_utils = NpmModulesUtils.return_value
        self.npm_modules_utils.pack_to_tar.side_effect = lambda actual_path: actual_path + '.tar'
        self.npm_modules_utils.clean_copy.side_effect = lambda actual_path, delete_package_lock: actual_path + '_copy'

        self.action = NodejsNpmRewriteLocalDependenciesAction(
            'work_dir',
            'original_package_dir',
            'scratch_dir',
            self.npm_modules_utils,
            self.osutils
        )

    def test_does_not_rewrite_if_no_local_dependencies(self):
        self.npm_modules_utils.get_local_dependencies.side_effect = [{}, {}]

        self.action.execute()

        self.npm_modules_utils.update_dependency.assert_not_called()

    def test_rewrites_a_single_production_dependency(self):
        def local_deps(work_dir, dependency_key):
            if work_dir == "work_dir" and dependency_key == "dependencies":
                return {"dep": "../dep"}
            else:
                return {}

        self.npm_modules_utils.get_local_dependencies.side_effect = local_deps

        self.action.execute()

        self.npm_modules_utils.update_dependency.assert_called_with(
            'work_dir', 'dep', 'file:original_package_dir/../dep_copy.tar', 'dependencies'
        )

    def test_rewrites_a_single_optional_dependency(self):
        def local_deps(work_dir, dependency_key):
            if work_dir == "work_dir" and dependency_key == "optionalDependencies":
                return {"dep": "../opt_dep"}
            else:
                return {}

        self.npm_modules_utils.get_local_dependencies.side_effect = local_deps

        self.action.execute()

        self.npm_modules_utils.update_dependency.assert_called_with(
            'work_dir', 'dep', 'file:original_package_dir/../opt_dep_copy.tar', 'optionalDependencies'
        )

    def test_strips_file_prefix_when_rewriting_dependencies(self):
        def local_deps(work_dir, dependency_key):
            if work_dir == "work_dir" and dependency_key == "dependencies":
                return {"dep": "file:/dep"}
            else:
                return {}

        self.npm_modules_utils.get_local_dependencies.side_effect = local_deps

        self.action.execute()

        self.osutils.joinpath.assert_called_with('original_package_dir', '/dep')

    def test_rewrites_production_dependencies_recursively(self):
        def local_deps(work_dir, dependency_key):
            if work_dir == 'work_dir' and dependency_key == 'dependencies':
                return {"dep": "../dep"}
            elif work_dir == 'original_package_dir/../dep_copy' and dependency_key == 'dependencies':
                return {"subdep": "../subdep"}
            else:
                return {}

        self.npm_modules_utils.get_local_dependencies.side_effect = local_deps

        self.action.execute()

        calls = [
            call(
                'original_package_dir/../dep_copy',
                'subdep',
                'file:original_package_dir/../dep/../subdep_copy.tar',
                'dependencies'
            ),
            call('work_dir', 'dep', 'file:original_package_dir/../dep_copy.tar', 'dependencies')
        ]
        self.npm_modules_utils.update_dependency.assert_has_calls(calls)
