"""
Cargo Lambda specific feature flag utilities
"""

EXPERIMENTAL_FLAG_CARGO_LAMBDA = "experimentalCargoLambda"


def is_experimental_cargo_lambda_scope(experimental_flags):
    """
    A function which will determine if experimental Cargo Lambda scope is active
    """
    return bool(experimental_flags) and EXPERIMENTAL_FLAG_CARGO_LAMBDA in experimental_flags
