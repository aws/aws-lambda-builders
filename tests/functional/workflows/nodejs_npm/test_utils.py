import pytest

import sys

import os

import shutil

import tempfile

from aws_lambda_builders.workflows.nodejs_npm import utils


@pytest.fixture
def osutils():
    return utils.OSUtils()


class TestOSUtils(object):
    def test_extract_tarfile_unpacks_a_tar(self, osutils):

        test_tar = os.path.join(os.path.dirname(__file__), "test_data", "test.tgz")

        test_dir = tempfile.mkdtemp()

        osutils.extract_tarfile(test_tar, test_dir)

        output_files = set(os.listdir(test_dir))

        shutil.rmtree(test_dir)

        assert {"test_utils.py"} == output_files

    def test_dirname_returns_directory_for_path(self, osutils):
        dirname = osutils.dirname(sys.executable)

        assert dirname == os.path.dirname(sys.executable)

    def test_abspath_returns_absolute_path(self, osutils):

        result = osutils.abspath('.')

        assert os.path.isabs(result)

        assert result == os.path.abspath('.')

    def test_joinpath_joins_path_components(self, osutils):

        result = osutils.joinpath('a', 'b', 'c')

        assert result == os.path.join('a', 'b', 'c')

    def test_popen_runs_a_process_and_returns_outcome(self, osutils):

        cwd_py = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'cwd.py')

        p = osutils.popen([sys.executable, cwd_py],
                          stdout=osutils.pipe,
                          stderr=osutils.pipe
                          )

        out, err = p.communicate()

        assert p.returncode == 0

        assert out.decode('utf8').strip() == os.getcwd()

    def test_popen_can_accept_cwd(self, osutils):

        testdata_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata')

        p = osutils.popen([sys.executable, 'cwd.py'],
                          stdout=osutils.pipe,
                          stderr=osutils.pipe,
                          cwd=testdata_dir)

        out, err = p.communicate()

        assert p.returncode == 0

        assert out.decode('utf8').strip() == os.path.abspath(testdata_dir)
