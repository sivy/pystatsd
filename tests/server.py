import unittest
import mock

# from pystatsd.statsd import Client
from pystatsd.server import Server


class ServerBasicsTestCase(unittest.TestCase):
    """
    Tests the basic operations of the client
    """
    def setUp(self):
        self.patchers = []

        socket_patcher = mock.patch('pystatsd.statsd.socket.socket')
        self.mock_socket = socket_patcher.start()
        self.patchers.append(socket_patcher)

    def test_server_create(self):
        server = Server()

        if getattr(self, "assertIsNotNone", False):
            self.assertIsNotNone(server)
        else:
            assert server is not None
