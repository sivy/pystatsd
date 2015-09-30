#!/usr/bin/env python

import time
from multiprocessing import Process

from pystatsd import Client, Server


def worker():
    srvr = Server(debug=True, flush_interval=500)
    srvr.serve()


p = Process(target=worker, daemon=False)
p.start()
time.sleep(1)


sc = Client('localhost', 8125)
sc.timing('python_test.time', 500)
sc.increment('python_test.inc_int')
sc.decrement('python_test.decr_int')
sc.gauge('python_test.gauge', 42)


time.sleep(2)
p.terminate()
