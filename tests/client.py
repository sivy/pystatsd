import time
import unittest
import mock
import socket
import sys

from pystatsd.statsd import Client


if sys.version_info[0] < 3:
    def bytes(s, encode):
        return s


class ClientBasicsTestCase(unittest.TestCase):
    """
    Tests the basic operations of the client
    """
    def setUp(self):
        self.patchers = []

        socket_patcher = mock.patch('pystatsd.statsd.socket.socket')
        self.mock_socket = socket_patcher.start()
        self.patchers.append(socket_patcher)

        self.client = Client()
        self.addr = (socket.gethostbyname(self.client.host), self.client.port)

    def test_client_create(self):
        host, port = ('example.com', 8888)

        client = Client(
            host=host,
            port=port,
            prefix='pystatsd.tests')
        self.assertEqual(client.host, host)
        self.assertEqual(client.port, port)
        self.assertEqual(client.prefix, 'pystatsd.tests')
        self.assertEqual(client.addr, (socket.gethostbyname(host), port))

    def test_basic_client_incr(self):
        stat = 'pystatsd.unittests.test_basic_client_incr'
        stat_str = stat + ':1|c'

        self.client.increment(stat)

        # thanks tos9 in #python for 'splaining the return_value bit.
        self.mock_socket.return_value.sendto.assert_called_with(
            bytes(stat_str, 'utf-8'), self.addr)

    def test_basic_client_decr(self):
        stat = 'pystatsd.unittests.test_basic_client_decr'
        stat_str = stat + ':-1|c'

        self.client.decrement(stat)

        # thanks tos9 in #python for 'splaining the return_value bit.
        self.mock_socket.return_value.sendto.assert_called_with(
            bytes(stat_str, 'utf-8'), self.addr)

    def test_basic_client_update_stats(self):
        stat = 'pystatsd.unittests.test_basic_client_update_stats'
        stat_str = stat + ':5|c'

        self.client.update_stats(stat, 5)

        # thanks tos9 in #python for 'splaining the return_value bit.
        self.mock_socket.return_value.sendto.assert_called_with(
            bytes(stat_str, 'utf-8'), self.addr)

    def test_basic_client_update_stats_multi(self):
        stats = [
            'pystatsd.unittests.test_basic_client_update_stats',
            'pystatsd.unittests.test_basic_client_update_stats_multi'
        ]

        data = dict((stat, "%s|c" % '5') for stat in stats)

        self.client.update_stats(stats, 5)

        for stat, value in data.items():
            stat_str = stat + value
            # thanks tos9 in #python for 'splaining the return_value bit.
            self.mock_socket.return_value.sendto.assert_call_any(
                bytes(stat_str, 'utf-8'), self.addr)

    def test_basic_client_timing(self):
        stat = 'pystatsd.unittests.test_basic_client_timing.time'
        stat_str = stat + ':5.000000|ms'

        self.client.timing(stat, 5)

        # thanks tos9 in #python for 'splaining the return_value bit.
        self.mock_socket.return_value.sendto.assert_called_with(
            bytes(stat_str, 'utf-8'), self.addr)

    def test_basic_client_timing_since(self):
        # arbitrary start timestamp value
        now = 1000.00
        # five and a half seconds later
        then = now + 5.5
        mock_time_patcher = mock.patch('time.time', return_value=now)
        mock_time_patcher.start()

        stat = 'pystatsd.unittests.test_basic_client_timing_since.time'
        stat_str = stat + ':-5500.000000|ms'

        self.client.timing_since(stat, then)

        # thanks tos9 in #python for 'splaining the return_value bit.
        self.mock_socket.return_value.sendto.assert_called_with(
            bytes(stat_str, 'utf-8'), self.addr)

        mock_time_patcher.stop()

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
