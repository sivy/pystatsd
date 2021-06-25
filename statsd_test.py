#!/usr/bin/env python

from statsd_to_logstash import Client, Server

sc = Client('localhost', 8125)

sc.timing('python_test.time', 500)
sc.increment('python_test.inc_int')
sc.decrement('python_test.decr_int')
sc.gauge('python_test.gauge', 42)

srvr = Server(debug=True)
srvr.serve()
