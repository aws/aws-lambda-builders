import os
import sys
import tempfile


def symlinks_supported() -> bool:
    """
    Returns True if the current platform and user are able to create symlinks.

    On Windows, os.symlink() requires either Administrator privileges or Developer
    Mode to be enabled (Windows 10+). Without either, it raises
    ``OSError: [WinError 1314] A required privilege is not held by the client``.
    Developer Mode is off by default, so this is the common case for a Windows
    contributor running the test suite locally.

    Returns
    -------
    bool
        True if os.symlink() is expected to succeed on this machine.
    """
    if sys.platform != "win32":
        return True
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "target")
        link = os.path.join(tmpdir, "link")
        open(target, "w").close()
        try:
            os.symlink(target, link)
        except OSError:
            return False
    return True


def read_link_without_junction_prefix(path: str) -> str:
    """
    When our tests run on CI on Windows, it seems to use junctions, which causes symlink targets
    have a prefix. This function reads a symlink and returns the target without the prefix (if any).

    Parameters
    ----------
    path : str
        Path which may or may not have a junction prefix.

    Returns
    -------
    str
        Path without junction prefix, if any.
    """
    target = os.readlink(path)
    if target.startswith("\\\\?\\"):  # \\?\, with escaped slashes
        target = target[4:]
    return target
