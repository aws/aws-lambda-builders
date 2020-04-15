import requests


def lambda_handler(event, context):
    # Just return the requests version.
    return "{}".format(requests.__version__)
