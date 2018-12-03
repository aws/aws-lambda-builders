import io

import pytest

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
