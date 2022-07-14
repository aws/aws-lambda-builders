"""
esbuild specific utilities and feature flag
"""
from typing import Optional, List

EXPERIMENTAL_FLAG_ESBUILD = "experimentalEsbuild"
EXPERIMENTAL_FLAG_BUILD_IMPROVEMENTS_22 = "experimentalBuildImprovements22"


def is_experimental_esbuild_scope(experimental_flags: Optional[List[str]]) -> bool:
    """
    A function which will determine if experimental esbuild scope is active
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_ESBUILD in experimental_flags


def is_experimental_build_improvements_enabled(experimental_flags: Optional[List[str]]) -> bool:
    """
    A function which will determine if experimental build improvements is active
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_BUILD_IMPROVEMENTS_22 in experimental_flags
