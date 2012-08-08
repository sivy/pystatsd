from statsd import Client
from server import Server

VERSION = (0, 1, 7)


def version():
    return ".".join(map(str, VERSION)),
