"""
Validation of Python Runtime Version
"""


def validate_python_cmd(required_language, required_runtime_version):
    major, minor = required_runtime_version.replace(required_language, "").split('.')
    cmd = [
        "python",
        "-c",
        "import sys; "
        "assert sys.version_info.major == {major} "
        "and sys.version_info.minor == {minor}".format(
            major=major,
            minor=minor)]
    return cmd
