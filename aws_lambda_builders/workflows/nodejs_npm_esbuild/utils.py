"""
esbuild specific utilities and feature flag
"""
import json
from typing import Dict, Any

EXPERIMENTAL_FLAG_ESBUILD = "experimentalEsbuild"


def is_experimental_esbuild_scope(experimental_flags):
    """
    A function which will determine if experimental esbuild scope is active
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_ESBUILD in experimental_flags


def parse_json(path: str) -> Dict[Any, Any]:
    """
    :type path: str
    :param path: path to JSON file

    :rtype: Dict[Any]
    :return: A loaded dict containing the JSON contents
    """
    with open(path) as json_file:
        return json.load(json_file)
