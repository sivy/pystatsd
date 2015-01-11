import time
import unittest
import mock
import socket
import sys

from pystatsd.backends import Graphite

class GraphiteBackendTestCase(unittest.TestCase):
    """
    Tests the basic operations of the Graphite backend
    """
    def setUp(self):
        self.patchers = []

        socket_patcher = mock.patch('pystatsd.backends.graphite.socket.socket')
        self.mock_socket = socket_patcher.start()
        self.patchers.append(socket_patcher)

        self.options = {
            'graphite_host': 'localhost',
            'graphite_port': 2003,
            'counters_prefix': 'stats',
            'timers_prefix': 'stats.timers',
            'global_prefix': None
        }
        
        self.config = {'debug': True, 'flush_interval': 10000, 'expire': 0, 'pct_threshold': 90}
        
        self.graphite = Graphite(self.options)
        self.graphite.init(self.config)

    def test_graphite_create(self):
        self.assertEqual(self.graphite.host, self.options['graphite_host'])
        self.assertEqual(self.graphite.port, self.options['graphite_port'])
        self.assertEqual(self.graphite.counters_prefix, self.options['counters_prefix'])
        self.assertEqual(self.graphite.timers_prefix, self.options['timers_prefix'])
        self.assertEqual(self.graphite.global_prefix, self.options['global_prefix'])
        
    def test_graphite_flush(self):
        ts = int(time.time())
        metrics = {
            'timers': {'glork': {
                'count': 1, 'max_threshold': 320.0, 'max': 320.0, 'min': 320.0,
                'pct_threshold': 90, 'mean': 320.0}
            },
            'gauges': {'gaugor': 333.0},
            'counters': {'gorets': 1.1}
        }
        
        self.graphite.flush(ts, metrics)
        
        # check connection information is correct
        self.mock_socket.return_value.connect.assert_called_with((
            self.options['graphite_host'], self.options['graphite_port']))
        
        # get sendall call argument
        sendall = self.mock_socket.return_value.mock_calls[1]
        self.assertEqual(sendall[0], 'sendall')
        self.assertEqual(len(sendall[1]), 1)
        
        data = sendall[1][0].decode("utf-8").strip().split("\n")

        # check each metric
        for metric in data:
            fields = metric.split()
            id = fields[0].split('.')
            
            if id[0] == 'statsd' and id[1] == 'numStats':
                self.assertEqual(int(fields[1]), len(metrics))
            else:
                self.assertEqual(id[0], self.options['counters_prefix'])
                
                # counters and gauges
                if len(id) == 2:
                    self.assertEqual(metrics.get('gauges').get(id[1]) 
                        or metrics.get('counters').get(id[1]), float(fields[1]))
                # timers
                elif len(id) == 4:
                    self.assertTrue(metrics.get('timers').get(id[2]) != None)
                
            # check timestamp
            self.assertEqual(int(fields[2]), ts)
            
        # check connection has been closed
        self.mock_socket.return_value.close.assert_called_with()

        
    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
