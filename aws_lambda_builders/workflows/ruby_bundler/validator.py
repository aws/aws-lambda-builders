"""
Ruby Runtime Validation
"""

import logging
import os
import subprocess

from aws_lambda_builders.exceptions import MisMatchRuntimeError

LOG = logging.getLogger(__name__)

class RubyRuntimeValidator(object):
    LANGUAGE = "ruby"
    SUPPORTED_RUNTIMES = {
        "ruby2.5"
    }

    def __init__(self, runtime, bundler):
        self.runtime = runtime
        self.bundler = bundler
        self._valid_runtime_path = None

    def has_runtime(self):
        """
        Checks if the runtime is supported.
        :param string runtime: Runtime to check
        :return bool: True, if the runtime is supported.
        """
        return self.runtime in self.SUPPORTED_RUNTIMES

    def validate(self, runtime_path):
        """
        Checks if the language supplied matches the required lambda runtime
        :param string runtime_path: path to bundler
        :raises MisMatchRuntimeError: Version mismatch of the language vs the required runtime
        """
        if not self.has_runtime():
            LOG.warning("'%s' runtime is not "
                        "a supported runtime", self.runtime)
            return None

        # bundle exec ruby -e "puts RUBY_VERSION"
        p = subprocess.Popen([self.bundler.bundler_exe, "exec", "ruby", "-e", '"unless RUBY_VERSION.match(/2\\.5\\.\\d/); exit(1); end"'],
                             cwd=os.getcwd(),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.communicate() # don't care about the output
        if p.returncode == 0:
            self._valid_runtime_path = self.bundler.bundler_exe
            return self._valid_runtime_path
        else:
            print("The command '" + self.bundler.bundler_exe + " exec ruby' returned exit code " + str(p.returncode))
            raise MisMatchRuntimeError(
                language=self.LANGUAGE,
                required_runtime=self.runtime,
                runtime_path=self.bundler.bundler_exe)

    @property
    def validated_runtime_path(self):
        return self._valid_runtime_path
