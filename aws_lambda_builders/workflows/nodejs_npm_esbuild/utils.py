"""
esbuild specific utilities and feature flag
"""
import json

EXPERIMENTAL_FLAG_ESBUILD = "experimentalEsbuild"


def is_experimental_esbuild_scope(experimental_flags):
    """
    A function which will determine if experimental esbuild scope is active
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_ESBUILD in experimental_flags


def parse_json(path):
    with open(path) as json_file:
        return json.load(json_file)
