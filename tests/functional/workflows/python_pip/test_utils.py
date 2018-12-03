import io

import pytest

import sys

import os

from aws_lambda_builders.workflows.python_pip import utils


@pytest.fixture
def osutils():
    return utils.OSUtils()


class TestOSUtils(object):
    def test_can_read_unicode(self, tmpdir, osutils):
        filename = str(tmpdir.join('file.txt'))
        checkmark = u'\2713'
        with io.open(filename, 'w', encoding='utf-16') as f:
            f.write(checkmark)

        content = osutils.get_file_contents(filename, binary=False,
                                            encoding='utf-16')
        assert content == checkmark

    def test_dirname_returns_directory_for_path(self, tmpdir, osutils):
        dirname = osutils.dirname(sys.executable)

        assert dirname == os.path.dirname(sys.executable)

    def test_abspath_returns_absolute_path(self, tmpdir, osutils):

        result = osutils.abspath('.')

        assert os.path.isabs(result)

        assert result == os.path.abspath('.')

    def test_popen_can_accept_cwd(self, tmpdir, osutils):

        testdata_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata')

        p = osutils.popen([sys.executable, 'cwd.py'],
                          stdout=osutils.pipe,
                          stderr=osutils.pipe,
                          cwd=testdata_dir)

        out, err = p.communicate()

        assert p.returncode == 0

        assert out.decode('utf8').strip() == os.path.abspath(testdata_dir)
