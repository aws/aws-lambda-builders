"""
Commonly used utilities
"""

import json
import os
import platform
import shutil
import subprocess
from typing import List, Optional

# sam-cli's ExperimentalFlag.NodejsMonorepo: its config key crosses the boundary as this string,
# in the experimental_flags list the workflow is constructed with
EXPERIMENTAL_FLAG_NODEJS_MONOREPO = "experimentalNodejsMonorepo"


def is_nodejs_monorepo_support_enabled(experimental_flags: Optional[List[str]]) -> bool:
    """
    Is the caller opted in to the npm monorepo handling?

    Here that means one thing: an in-source install honours the lockfile npm will actually read, which
    in a workspaces monorepo is the root's rather than the function's. Without the flag the install is
    the `npm update --no-package-lock` every release so far has run, so a release can carry this change
    while the default path stays exactly as it was.

    Opting in does NOT yet make this workflow usable for a monorepo. The install resolves correctly, but
    the artifacts link still looks beside the function, where npm hoisting leaves nothing, so the package
    it produces has no dependencies in it - aws/aws-lambda-builders#933, fixed separately on this same
    flag. Until that lands, the flag buys a correct install and nothing about the artifacts.
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_NODEJS_MONOREPO in experimental_flags


class OSUtils(object):
    """
    Wrapper around file system functions, to make it easy to
    unit test actions in memory
    """

    def copy_file(self, file_path, destination_path):
        return shutil.copy2(file_path, destination_path)

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def joinpath(self, *args):
        return os.path.join(*args)

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    @property
    def pipe(self):
        return subprocess.PIPE

    def dirname(self, path):
        return os.path.dirname(path)

    def remove_file(self, filename):
        return os.remove(filename)

    def abspath(self, path):
        return os.path.abspath(path)

    def is_windows(self):
        return platform.system().lower() == "windows"

    def parse_json(self, path):
        with open(path) as json_file:
            return json.load(json_file)

    def check_output(self, path):
        return subprocess.check_output(["node", path])
