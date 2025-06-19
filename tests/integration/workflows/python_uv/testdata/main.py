import six


def lambda_handler(event, context):
    return {"statusCode": 200, "body": f"Six version: {six.__version__}"}
