from unittest import TestCase
from mock import patch

from aws_lambda_builders.workflows.dotnet_clipackage.dotnetcli_resolver import DotnetCliResolver


class TestDotnetCliResolver(TestCase):
    @patch("aws_lambda_builders.workflows.dotnet_clipackage.utils.OSUtils")
    def setUp(self, MockOSUtils):
        self.os_utils = MockOSUtils.return_value

    def test_found_windows(self):
        self.os_utils.reset_mock()

        self.os_utils.which.side_effect = ["c:/dir/dotnet.exe"]

        resolver = DotnetCliResolver(os_utils=self.os_utils)
        found = resolver.exec_paths

        self.assertEqual("c:/dir/dotnet.exe", found)

    def test_found_linux(self):
        self.os_utils.reset_mock()

        self.os_utils.which.side_effect = [None, "/usr/dotnet/dotnet"]

        resolver = DotnetCliResolver(os_utils=self.os_utils)
        found = resolver.exec_paths

        self.assertEqual("/usr/dotnet/dotnet", found)

    def test_not_found(self):
        self.os_utils.reset_mock()
        self.os_utils.which.side_effect = [None, None]
        resolver = DotnetCliResolver(os_utils=self.os_utils)
        self.assertRaises(ValueError, self.exec_path_method_wrapper, resolver)

    def exec_path_method_wrapper(self, resolver):
        resolver.exec_paths
