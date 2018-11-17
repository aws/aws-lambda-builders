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

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowNotFoundError, WorkflowUnknownError, WorkflowFailedError


log_level = int(os.environ.get("LAMBDA_BUILDERS_LOG_LEVEL", logging.INFO))

# Write output to stderr because stdout is used for command response
logging.basicConfig(stream=sys.stderr,
                    level=log_level,
                    format='%(message)s')

LOG = logging.getLogger(__name__)


def _success_response(request_id, artifacts_dir):
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "artifacts_dir": artifacts_dir
        }
    })


def _error_response(request_id, http_status_code, message):
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": http_status_code,
            "message": message
        }
    })


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

    capabilities = params["capability"]
    supported_workflows = params.get("supported_workflows")

    exit_code = 0
    response = None
    try:
        builder = LambdaBuilder(language=capabilities["language"],
                                dependency_manager=capabilities["dependency_manager"],
                                application_framework=capabilities["application_framework"],
                                supported_workflows=supported_workflows)

        artifacts_dir = params["artifacts_dir"]
        builder.build(params["source_dir"],
                      params["artifacts_dir"],
                      params["scratch_dir"],
                      params["manifest_path"],
                      runtime=params["runtime"],
                      optimizations=params["optimizations"],
                      options=params["options"])

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


if __name__ == '__main__':
    main()
