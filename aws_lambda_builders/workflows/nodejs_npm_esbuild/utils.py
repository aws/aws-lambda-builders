"""
esbuild specific utilities and feature flag
"""

EXPERIMENTAL_FLAG_ESBUILD = "experimentalEsbuild"


def is_experimental_esbuild_scope(experimental_flags):
    """
    A function which will determine if experimental esbuild scope is active
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_ESBUILD in experimental_flags


def get_typescript_file_type(entry_path):
    """
    Append a TypeScript file suffix to a path
    """
    return entry_path + ".ts"


def get_javascript_file_type(entry_path):
    """
    Append a JavaScript file suffix to a path
    """
    return entry_path + ".js"
