"""
No-op validator that does not validate the runtime_path for a specified language.
"""

import logging

LOG = logging.getLogger(__name__)


class RuntimeValidator(object):
    def __init__(self, runtime):
        self.runtime = runtime
        self._runtime_path = None

    def validate(self, runtime_path):
        self._runtime_path = runtime_path
        return runtime_path
