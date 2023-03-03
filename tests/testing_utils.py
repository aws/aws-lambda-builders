import os


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
