"""
CLI interface for AWS Lambda Builder. It is a very thin wrapper over the library. It is meant to integrate
with tools written in other programming languages that can't import Python libraries directly. The CLI provides
a JSON-RPC interface over stdin/stdout to invoke the builder and get response.

Read the design document for explanation of the JSON-RPC interface
"""

import sys
import json
import os
import logging
import re

from aws_lambda_builders.architecture import X86_64
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowNotFoundError, WorkflowUnknownError, WorkflowFailedError
from aws_lambda_builders import RPC_PROTOCOL_VERSION as lambda_builders_protocol_version

log_level = int(os.environ.get("LAMBDA_BUILDERS_LOG_LEVEL", logging.INFO))

# Write output to stderr because stdout is used for command response
logging.basicConfig(stream=sys.stderr, level=log_level, format="%(message)s")

LOG = logging.getLogger(__name__)

VERSION_REGEX = re.compile("^([0-9])+.([0-9]+)$")


def _success_response(request_id, artifacts_dir):
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {"artifacts_dir": artifacts_dir}})


def _error_response(request_id, http_status_code, message):
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": http_status_code, "message": message}})


def _parse_version(version_string):

    if VERSION_REGEX.match(version_string):
        return float(version_string)
    else:
        ex = "Protocol Version does not match : {}".format(VERSION_REGEX.pattern)
        LOG.debug(ex)
        raise ValueError(ex)


def version_compatibility_check(version):
    # The following check is between current protocol version vs version of the protocol
    # with which aws-lambda-builders is called.
    # Example:
    # 0.2 < 0.2 comparison will fail, don't throw a value Error saying incompatible version.
    # 0.2 < 0.3 comparison will pass, throwing a ValueError
    # 0.2 < 0.1 comparison will fail, don't throw a value Error saying incompatible version

    if _parse_version(lambda_builders_protocol_version) < version:
        ex = "Incompatible Protocol Version : {}, " "Current Protocol Version: {}".format(
            version, lambda_builders_protocol_version
        )
        LOG.error(ex)
        raise ValueError(ex)


def _write_response(response, exit_code):
    sys.stdout.write(response)
    sys.stdout.flush()  # Make sure it is written
    sys.exit(exit_code)


def main():  # pylint: disable=too-many-statements
    """
    Implementation of CLI Interface. Handles only one JSON-RPC method at a time and responds with data

    Input is passed as JSON string either through stdin or as the first argument to the command. Output is always
    printed to stdout.
    """

    # For now the request is not validated
    if len(sys.argv) > 1:
        request_str = sys.argv[1]
        LOG.debug("Using the request object from command line argument")
    else:
        LOG.debug("Reading the request object from stdin")
        request_str = sys.stdin.read()

    request = json.loads(request_str)
    request_id = request["id"]
    params = request["params"]

    # Currently, this is the only supported method
    if request["method"] != "LambdaBuilder.build":
        response = _error_response(request_id, -32601, "Method unavailable")
        return _write_response(response, 1)

    try:
        protocol_version = _parse_version(params.get("__protocol_version"))
        version_compatibility_check(protocol_version)

    except ValueError:
        response = _error_response(request_id, 505, "Unsupported Protocol Version")
        return _write_response(response, 1)

    capabilities = params["capability"]
    supported_workflows = params.get("supported_workflows")

    exit_code = 0
    response = None

    try:
        builder = LambdaBuilder(
            language=capabilities["language"],
            dependency_manager=capabilities["dependency_manager"],
            application_framework=capabilities["application_framework"],
            supported_workflows=supported_workflows,
        )

        artifacts_dir = params["artifacts_dir"]
        builder.build(
            params["source_dir"],
            params["artifacts_dir"],
            params["scratch_dir"],
            params["manifest_path"],
            executable_search_paths=params.get("executable_search_paths", None),
            runtime=params["runtime"],
            optimizations=params["optimizations"],
            options=params["options"],
            mode=params.get("mode", None),
            download_dependencies=params.get("download_dependencies", True),
            dependencies_dir=params.get("dependencies_dir", None),
            combine_dependencies=params.get("combine_dependencies", True),
            architecture=params.get("architecture", X86_64),
            is_building_layer=params.get("is_building_layer", False),
            experimental_flags=params.get("experimental_flags", []),
        )

        # Return a success response
        response = _success_response(request_id, artifacts_dir)

    except (WorkflowNotFoundError, WorkflowUnknownError, WorkflowFailedError) as ex:
        LOG.debug("Builder workflow failed", exc_info=ex)
        exit_code = 1
        response = _error_response(request_id, 400, str(ex))

    except Exception as ex:
        LOG.debug("Builder crashed", exc_info=ex)
        exit_code = 1
        response = _error_response(request_id, 500, str(ex))

    _write_response(response, exit_code)


if __name__ == "__main__":
    main()
