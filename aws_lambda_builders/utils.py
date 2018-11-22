"""
Common utilities for the library
"""

import shutil
import sys
import os
import logging


LOG = logging.getLogger(__name__)


def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.

    """

    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode)
                and not os.path.isdir(fn))

    # If we're given a path with a directory part, look it up directly rather
    # than referring to PATH directories. This includes checking relative to the
    # current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd
        return None

    if path is None:
        path = os.environ.get("PATH", os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if not os.curdir in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path extensions.
        # This will allow us to short circuit when given "python.exe".
        # If it does match, only test that one, otherwise we have to try
        # others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir in path:
        normdir = os.path.normcase(dir)
        if not normdir in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir, thefile)
                if _access_check(name, mode):
                    return name
    return None

def copytree(source, destination, ignore=None):
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
    """

    if not os.path.exists(destination):
        os.makedirs(destination)

        try:
            # Let's try to copy the directory metadata from source to destination
            shutil.copystat(source, destination)
        except WindowsError as ex:  # pylint: disable=undefined-variable
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
            continue

        new_source = os.path.join(source, name)
        new_destination = os.path.join(destination, name)

        if os.path.isdir(new_source):
            copytree(new_source, new_destination, ignore=ignore)
        else:
            shutil.copy2(new_source, new_destination)
