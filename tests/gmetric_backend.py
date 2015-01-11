import time
import unittest
import mock
import socket
import sys

from pystatsd.backends import Gmetric

class GmetricBackendTestCase(unittest.TestCase):
    """
    Tests the basic operations of the Ganglia backend
    """
    def setUp(self):
        self.patchers = []

        gmetric_patcher = mock.patch('pystatsd.backends.gmetric.call')
        self.mock_gmetric = gmetric_patcher.start()
        self.patchers.append(gmetric_patcher)

        self.options = {
            'gmetric_exec': '/usr/bin/gmetric',
            'gmetric_options': '-d'
        }
        
        self.config = {'debug': True, 'flush_interval': 10000, 'expire': 0, 'pct_threshold': 90}
        
        self.gmetric = Gmetric(self.options)
        self.gmetric.init(self.config)

    def test_ganglia_create(self):
        self.assertEqual(self.gmetric.gmetric_exec, self.options['gmetric_exec'])
        self.assertEqual(self.gmetric.gmetric_options, self.options['gmetric_options'])
        
    def test_ganglia_flush(self):
        ts = int(time.time())
        metrics = {
            'timers': {'glork': {
                'count': 1, 'max_threshold': 320.0, 'max': 320.0, 'min': 320.0,
                'pct_threshold': 90, 'mean': 320.0}
            },
            'gauges': {'gaugor': 333.0},
            'counters': {'gorets': 1.1}
        }
        
        self.gmetric.flush(ts, metrics)
        
        self.mock_gmetric.assert_any_call(self._send_args('gorets', 1.1, "_counters", "count"))
        self.mock_gmetric.assert_any_call(self._send_args('gaugor', 333.0, "_gauges", "gauge"))
        
        for m in ['min', 'max', 'mean', '90pct']:
            self.mock_gmetric.assert_any_call(self._send_args('glork_'+m, 0.32, "glork", "seconds"))
            
        self.mock_gmetric.assert_any_call(self._send_args('glork_count', 1, 'glork', 'count'))

    def _send_args(self, k, v, group, units):
        return [self.options['gmetric_exec'], self.options['gmetric_options'],
                "-u", units, "-g", group, "-t", "double", "-n",  k, "-v", str(v)]
            
    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
