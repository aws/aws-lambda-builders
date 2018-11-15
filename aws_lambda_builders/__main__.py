"""
CLI interface for AWS Lambda Builder. It is a very thin wrapper over the library. It is meant to integrate
with tools written in other programming languages that can't import Python libraries directly. The CLI provides
a JSON-RPC interface over stdin/stdout to invoke the builder and get response.

Read the design document for explanation of the JSON-RPC interface
"""

import sys
import json
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowNotFoundError, WorkflowUnknownError, WorkflowFailedError


def _success_response(request_id):
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {}
    })


def main():
    """
    Implementation of CLI Interface. Handles only one JSON-RPC method at a time and responds with data

    Input is passed as JSON string either through stdin or as the first argument to the command. Output is always
    printed to stdout.
    """

    # For now the request is not validated
    if len(sys.argv) > 1:
        request_str = sys.argv[1]
    else:
        request_str = sys.stdin.read()

    request = json.loads(request_str)

    request_id = request["id"]
    params = request["params"]
    capabilities = params["capability"]
    supported_workflows = params["supported_workflows"]

    try:
        builder = LambdaBuilder(language=capabilities["language"],
                                dependency_manager=capabilities["dependency_manager"],
                                application_framework=capabilities["application_framework"],
                                supported_workflows=supported_workflows)

        builder.build(params["source_dir"],
                      params["artifacts_dir"],
                      params["scratch_dir"],
                      params["manifest_path"],
                      runtime=params["runtime"],
                      optimizations=params["optimizations"],
                      options=params["options"])

        # Return a success response
        sys.stdout.write(_success_response(request_id))
        sys.stdout.flush()  # Make sure it is written

    except (WorkflowNotFoundError, WorkflowUnknownError, WorkflowFailedError) as ex:
        # TODO: Return a workflow error response
        print(str(ex))
        sys.exit(1)
    except Exception as ex:
        # TODO: Return a internal server response
        print(str(ex))
        sys.exit(1)


if __name__ == '__main__':
    main()
