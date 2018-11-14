import numpy


def lambda_handler(event, context):
    # Just return the value of PI with two decimals - 3.14
    return "{0:.2f}".format(numpy.pi)
