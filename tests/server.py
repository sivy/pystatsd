import unittest
import mock
import socket
import threading

from pystatsd.server import Server
from pystatsd.backends import Console

from mock import Mock, ANY
from time import sleep

class ServerBasicsTestCase(unittest.TestCase):
    """
    Tests the basic operations of the server
    """
    def setUp(self):
        self.addr = (socket.gethostbyname(''), 8125)
        self.backend = self.__create_backend()

    def test_server_create(self):
        """Create a new server and checks if initialization is correct"""
        server = Server(backends=[self.backend])

        if getattr(self, "assertIsNotNone", False):
            self.assertIsNotNone(server)
        else:
            assert server is not None
        
        self.assertEqual(server.expire, 0)
        self.assertEqual(server.buf, 8192)
        self.assertEqual(len(server.backends), 1)
        self.assertEqual(len(server.counters), 0)
        self.assertEqual(len(server.timers), 0)
        self.assertEqual(len(server.gauges), 0)
        
        self.backend.init.assert_called_with({
            'debug': False,
            'flush_interval': 10000
        })
        
    def test_server_process(self):
        """
        Checks if the server is properly processing the different types of metrics.
        """
        server = Server()
        server.process('gorets:1|c\nglork:320|ms\ngaugor:333|g')

        self.assertEqual(len(server.counters), 1)
        self.assertEqual(server.counters.get('gorets')[0], 1.0)
        self.assertEqual(len(server.timers), 1)
        self.assertEqual(server.timers.get('glork')[0], [320.0])
        self.assertEqual(len(server.gauges), 1)
        self.assertEqual(server.gauges.get('gaugor')[0], 333.0)
        
        server.process('gorets:1|c|@0.1')
        self.assertEqual(len(server.counters), 1)
        self.assertEqual(server.counters.get('gorets')[0], 11.0)
        
    def test_server_flush(self):
        """
        Checks if the backend is receiving the processed metrics properly after 
        a flush.
        """
        server = Server(backends=[self.backend])
        server.process('gorets:1|c\ngorets:1|c|@0.1\nglork:320|ms\ngaugor:333|g')
        
        server.flush()
        self.backend.flush.assert_called_with(ANY,  {
            'timers': {'glork': {
                'count': 1, 'max_threshold': 320.0, 'max': 320.0, 'min': 320.0,
                'pct_threshold': 90, 'mean': 320.0}
            },
            'gauges': {'gaugor': 333.0},
            'counters': {'gorets': 1.1}
        })
        
        server.flush()
        self.backend.flush.assert_called_with(ANY,  {
            'timers': {}, 'gauges': {'gaugor': 333.0}, 'counters': {}})
        
        self.assertEqual(len(server.gauges), 1)
        self.assertEqual(len(server.timers), 0)
        self.assertEqual(len(server.counters), 0)
        
    def test_server_flush_del_gauges(self):
        """
        Checks if all metrics are removed after a flush with a server set to delete
        gauges.
        """
        server = Server(deleteGauges=True, backends=[self.backend])
        server.process('gorets:1|c\ngorets:1|c|@0.1\nglork:320|ms\ngaugor:333|g')
        server.flush()
        
        self.backend.flush.assert_called_with(ANY,  {
            'timers': {'glork': {
                'count': 1, 'max_threshold': 320.0, 'max': 320.0, 'min': 320.0,
                'pct_threshold': 90, 'mean': 320.0}
            },
            'gauges': {'gaugor': 333.0},
            'counters': {'gorets': 1.1}
        })
            
        self.assertEqual(len(server.gauges), 0)
        self.assertEqual(len(server.timers), 0)
        self.assertEqual(len(server.counters), 0)
        
    def test_server_flush_backends(self):
        """
        Test a server with multiple backends and ensures that all of them are 
        called after a flush.
        """
        backend_a = self.__create_backend()
        backend_b = self.__create_backend()

        server = Server(backends=[backend_a, backend_b])
        server.flush()
        
        metrics = {'timers': {}, 'gauges': {}, 'counters': {}}
        backend_a.flush.assert_called_with(ANY, metrics)
        backend_b.flush.assert_called_with(ANY, metrics)
        
    def test_server_flush_expire(self):
        """
        Test if metrics are removed by forcing them to expire.
        """
        server = Server(expire=1, backends=[self.backend])
        server.process('gorets:1|c\ngorets:1|c|@0.1\nglork:320|ms\ngaugor:333|g')
        
        sleep(2)
        server.flush()        
        self.assertEqual(len(server.gauges), 0)
        self.assertEqual(len(server.timers), 0)
        self.assertEqual(len(server.counters), 0)
        
        
    def __create_backend(self):
        backend = Console()
        backend.init  = Mock()
        backend.flush = Mock()
        return backend
