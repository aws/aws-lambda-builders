from elftools.elf.elffile import ELFFile
import hashlib


def get_executable_arch(path):
    """
    Returns the architecture of an executable binary

    Parameters
    ----------
    path : str
        path to the Go binaries generated

    Returns
    -------
    str
        Architecture type of the generated binaries
    """
    with open(str(path), "rb") as f:
        e = ELFFile(f)
        return e.get_machine_arch()


def get_md5_hexdigest(path):
    """
    Returns the hexdigest of a binary

    Parameters
    ----------
    path : str
        path to the Go binaries generated

    Returns
    -------
    str
        Hex digest of the binaries
    """
    with open(str(path), "rb") as f:
        hashed = hashlib.md5(f.read())
        return hashed.hexdigest()
