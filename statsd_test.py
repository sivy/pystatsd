#!/usr/bin/env python

from pystatsd import Client, Server
from pystatsd.backends import Console

sc = Client('localhost', 8125)

sc.timing('python_test.time', 500)
sc.increment('python_test.inc_int')
sc.decrement('python_test.decr_int')
sc.gauge('python_test.gauge', 42)

srvr = Server(debug=True, flush_interval=2000, deleteGauges=True, backends=[Console()])
srvr.serve()
