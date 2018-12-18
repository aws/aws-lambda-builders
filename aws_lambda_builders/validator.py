"""
No-op validator that does not validate the runtime_path for a specified language.
"""

import logging

LOG = logging.getLogger(__name__)


class RuntimeValidator(object):

    def __init__(self, runtime_path):
        self.runtime_path = runtime_path

    def validate_runtime(self):
        pass
