import time
import unittest
import mock
import socket
import sys

from pystatsd.backends import Ganglia

class GangliaBackendTestCase(unittest.TestCase):
    """
    Tests the basic operations of the Ganglia backend
    """
    def setUp(self):
        self.patchers = []

        gmetric_patcher = mock.patch('pystatsd.backends.ganglia.gmetric.Gmetric')
        self.mock_gmetric = gmetric_patcher.start()
        self.patchers.append(gmetric_patcher)

        self.options = {
            'ganglia_host': 'localhost',
            'ganglia_port': 8649,
            'ganglia_protocol': 'udp',
            'ganglia_spoof_host': 'statsd:statsd'
        }
        
        self.config = {'debug': True, 'flush_interval': 10000, 'expire': 0, 'pct_threshold': 90}
        
        self.ganglia = Ganglia(self.options)
        self.ganglia.init(self.config)

    def test_ganglia_create(self):
        self.assertEqual(self.ganglia.host, self.options['ganglia_host'])
        self.assertEqual(self.ganglia.port, self.options['ganglia_port'])
        self.assertEqual(self.ganglia.protocol, self.options['ganglia_protocol'])
        self.assertEqual(self.ganglia.spoof_host, self.options['ganglia_spoof_host'])
        self.assertEqual(self.ganglia.dmax, int(self.config['flush_interval']*1.2))
        
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
        
        self.ganglia.flush(ts, metrics)
        
        self.mock_gmetric.assert_called_with(
            self.options['ganglia_host'], self.options['ganglia_port'], self.options['ganglia_protocol'])
            
        send_fn = self.mock_gmetric.return_value.send
            
        send_fn.assert_any_call('gorets', 1.1, "double", "count", "both", 60, 
            self.ganglia.dmax, "_counters", self.ganglia.spoof_host)
        send_fn.assert_any_call('gaugor', 333.0, "double", "count", "both", 60, 
            self.ganglia.dmax, "_gauges", self.ganglia.spoof_host)
            
        for m in ['min', 'max', 'mean', '90pct']:
            send_fn.assert_any_call('glork_'+m, 0.32, 'double', 'seconds', 'both',
                60, self.ganglia.dmax, 'glork',  self.ganglia.spoof_host)
                
        send_fn.assert_any_call('glork_count', 1, 'double', 'count', 'both',
            60, self.ganglia.dmax, 'glork',  self.ganglia.spoof_host)
            
    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
