# statsd.py

# Steve Ivy <steveivy@gmail.com>
# http://monkinetic.com

import contextlib
import logging
import socket
import random
import time


# Sends statistics to the stats daemon over UDP
class Client(object):

    def __init__(self, host='localhost', port=8125, prefix=None):
        """
        Create a new Statsd client.
        * host: the host where statsd is listening, defaults to localhost
        * port: the port where statsd is listening, defaults to 8125

        >>> from pystatsd import statsd
        >>> stats_client = statsd.Statsd(host, port)
        """
        self.host = host
        self.port = int(port)
        self.addr = (socket.gethostbyname(self.host), self.port)
        self.prefix = prefix
        self.log = logging.getLogger("pystatsd.client")
        self.log.addHandler(logging.StreamHandler())
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    @contextlib.contextmanager
    def timer(self, stats, sample_rate=1):
        start = time.time()
        yield
        self.timing_since(stats, start, sample_rate)

    def timing_since(self, stats, start, sample_rate=1):
        """
        Log timing information as the number of milliseconds since the provided time float
        >>> start = time.time()
        >>> # do stuff
        >>> statsd_client.timing_since('some.time', start)
        """
        self.timing(stats, (time.time() - start) * 1000, sample_rate)

    def timing(self, stats, time, sample_rate=1):
        """
        Log timing information for one or more stats, in milliseconds
        >>> statsd_client.timing('some.time', 500)
        """
        if not isinstance(stats, list):
            stats = [stats]

        data = dict((stat, "%f|ms" % time) for stat in stats)
        self.send(data, sample_rate)

    def gauge(self, stats, value, sample_rate=1):
        """
        Log gauge information for a single stat
        >>> statsd_client.gauge('some.gauge',42)
        """
        if not isinstance(stats, list):
            stats = [stats]

        data = dict((stat, "%f|g" % value) for stat in stats)
        self.send(data, sample_rate)

    def increment(self, stats, sample_rate=1):
        """
        Increments one or more stats counters
        >>> statsd_client.increment('some.int')
        >>> statsd_client.increment('some.int',0.5)
        """
        self.update_stats(stats, 1, sample_rate=sample_rate)

    # alias
    incr = increment

    def decrement(self, stats, sample_rate=1):
        """
        Decrements one or more stats counters
        >>> statsd_client.decrement('some.int')
        """
        self.update_stats(stats, -1, sample_rate=sample_rate)

    # alias
    decr = decrement

    def update_stats(self, stats, delta, sample_rate=1):
        """
        Updates one or more stats counters by arbitrary amounts
        >>> statsd_client.update_stats('some.int',10)
        """
        if not isinstance(stats, list):
            stats = [stats]

        data = dict((stat, "%s|c" % delta) for stat in stats)
        self.send(data, sample_rate)

    def send(self, data, sample_rate=1):
        """
        Squirt the metrics over UDP
        """

        if self.prefix:
            data = dict((".".join((self.prefix, stat)), value) for stat, value in data.items())

        if sample_rate < 1:
            if random.random() > sample_rate:
                return
            sampled_data = dict((stat, "%s|@%s" % (value, sample_rate))
                                for stat, value in data.items())
        else:
            sampled_data = data

        try:
            [self.udp_sock.sendto(bytes(bytearray("%s:%s" % (stat, value),
                                                  "utf-8")), self.addr)
             for stat, value in sampled_data.items()]
        except:
            self.log.exception("unexpected error")

    def __repr__(self):
        return "<pystatsd.statsd.Client addr=%s prefix=%s>" % (self.addr, self.prefix)
