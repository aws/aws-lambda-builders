
import shutil
import os


def copytree(source, destination, ignore=None):
    """
    Similar to shutil.copytree except that it removes the limitation that the destination directory should
    be present.

    :param source:
    :param destination:
    :param ignore:
    :return:
    """

    if not os.path.exists(destination):
        os.makedirs(destination)

        try:
            # Let's try to copy the directory metadata from source to destination
            shutil.copystat(source, destination)
        except WindowsError:
            # Can't copy file access times in Windows
            pass

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


