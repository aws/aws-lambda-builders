"""
Common utilities for the library
"""

import shutil
import sys
import os
import logging

from aws_lambda_builders.architecture import X86_64, ARM64

LOG = logging.getLogger(__name__)


def copytree(source, destination, ignore=None, include=None):
    """
    Similar to shutil.copytree except that it removes the limitation that the destination directory should
    be present.

    :type source: str
    :param source:
        Path to the source folder to copy

    :type destination: str
    :param destination:
        Path to destination folder

    :type ignore: function
    :param ignore:
        A function that returns a set of file names to ignore, given a list of available file names. Similar to the
        ``ignore`` property of ``shutils.copytree`` method

    :type include: Callable[[str], bool]
    :param include:
        A function that will decide whether a file should be copied or skipped it. It accepts file name as parameter
        and return True or False. Returning True will continue copy operation, returning False will skip copy operation
        for that file
    """

    if not os.path.exists(source):
        LOG.warning("Skipping copy operation since source %s does not exist", source)
        return

    if not os.path.exists(destination):
        LOG.debug("Creating target folders at %s", destination)
        os.makedirs(destination)

        try:
            # Let's try to copy the directory metadata from source to destination
            LOG.debug("Copying directory metadata from source (%s) to destination (%s)", source, destination)
            shutil.copystat(source, destination)
        except OSError as ex:
            # Can't copy file access times in Windows
            LOG.debug("Unable to copy file access times from %s to %s", source, destination, exc_info=ex)

    names = os.listdir(source)
    if ignore is not None:
        ignored_names = ignore(source, names)
    else:
        ignored_names = set()

    for name in names:
        # Skip ignored names
        if name in ignored_names:
            LOG.debug("File (%s) is in ignored set, skipping it", name)
            continue

        new_source = os.path.join(source, name)
        new_destination = os.path.join(destination, name)

        if include and not os.path.isdir(new_source) and not include(name):
            LOG.debug("File (%s) doesn't satisfy the include rule, skipping it", name)
            continue

        if os.path.isdir(new_source):
            copytree(new_source, new_destination, ignore=ignore, include=include)
        else:
            LOG.debug("Copying source file (%s) to destination (%s)", new_source, new_destination)
            shutil.copy2(new_source, new_destination)


# NOTE: The below function is copied from Python source code and modified
# slightly to return a list of paths that match a given command
#  instead of returning just the first match

# The function "which" at aws_lambda_builders/utils.py was copied from https://github.com/python/cpython/blob/3.7/Lib/shutil.py
# SPDX-License-Identifier: Python-2.0
# Copyright 2019 by the Python Software Foundation


def which(cmd, mode=os.F_OK | os.X_OK, executable_search_paths=None):  # pragma: no cover
    """Given a command, mode, and executable search paths list, return the paths which
    conforms to the given mode on the PATH with the prepended additional search paths,
    or None if there is no such file.
    `mode` defaults to os.F_OK | os.X_OK. the default search `path` defaults
    to the result of os.environ.get("PATH")
    Note: This function was backported from the Python 3 source code.

    :type cmd: str
    :param cmd:
        Executable to be looked up in PATH.

    :type mode: str
    :param mode:
        Modes of access for the executable.

    :type executable_search_paths: list
    :param executable_search_paths:
        List of paths to look for `cmd` in preference order.
    """

    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.

    def _access_check(fn, mode):
        return os.path.exists(fn) and os.access(fn, mode) and not os.path.isdir(fn)

    # If we're given a path with a directory part, look it up directly
    # rather than referring to PATH directories. This includes checking
    # relative to the current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd

        return None

    path = os.environ.get("PATH", os.defpath)

    if not path:
        return None

    path = path.split(os.pathsep)

    if executable_search_paths:
        path = executable_search_paths + path

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if os.curdir not in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path
        # extensions. This will allow us to short circuit when given
        # "python.exe". If it does match, only test that one, otherwise we
        # have to try others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    paths = []

    for dir in path:
        normdir = os.path.normcase(dir)
        if normdir not in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir, thefile)
                if _access_check(name, mode):
                    paths.append(name)
    return paths


def get_goarch(architecture):
    """
    Parameters
    ----------
    architecture : str
        name of the type of architecture

    Returns
    -------
    str
        returns a valid GO Architecture value
    """
    return "arm64" if architecture == ARM64 else "amd64"
