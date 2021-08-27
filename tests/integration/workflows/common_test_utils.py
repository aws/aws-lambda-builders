import os
from zipfile import ZipFile


def does_folder_contain_all_files(folder, files):
    for f in files:
        if not does_folder_contain_file(folder, f):
            return False
    return True


def does_folder_contain_file(folder, file):
    return os.path.exists(os.path.join(folder, file))


def does_zip_contain_all_files(zip_path, files):
    with ZipFile(zip_path) as z:
        zip_names = set(z.namelist())
        return set(files).issubset(zip_names)
