from elftools.elf.elffile import ELFFile


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
