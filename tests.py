import unittest2
import mock
import socket

import pystatsd
from pystatsd import Client


class GoodConnectionTestCase(unittest2.TestCase):

    def setUp(self):
        self.patchers = []

        socket_patcher = mock.patch('pystatsd.statsd.socket.socket')
        self.mock_socket = socket_patcher.start()
        print self.mock_socket.sendto
        self.patchers.append(socket_patcher)

    def test_basic_client(self):
        client = Client()

        client.increment('pystatsd.unittests.test_basic_client')
        print self.mock_socket.sendto.call_args
        # self.mocket.sendto.assert_called_with()

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
