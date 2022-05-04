"""
Commonly used utilities
"""

EXPERIMENTAL_MAVEN_SCOPE_AND_LAYER_FLAG = "experimentalMavenScopeAndLayer"


def jar_file_filter(file_name):
    """
    A function that will filter .jar files for copy operation

    :type file_name: str
    :param file_name:
        Name of the file that will be checked against if it ends with .jar or not
    """
    return bool(file_name) and isinstance(file_name, str) and file_name.endswith(".jar")


def is_experimental_maven_scope_and_layers_active(experimental_flags):
    """
    A function which will determine if experimental maven scope and layer changes are active
    """
    return bool(experimental_flags) and EXPERIMENTAL_MAVEN_SCOPE_AND_LAYER_FLAG in experimental_flags
