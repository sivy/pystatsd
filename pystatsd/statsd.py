# statsd.py

# Steve Ivy <steveivy@gmail.com>
# http://monkinetic.com

import logging
import socket
import random

# Sends statistics to the stats daemon over UDP
class Client(object):
    
    def __init__(self, host='localhost', port=8125):
        """
        Create a new Statsd client.
        * host: the host where statsd is listening, defaults to localhost
        * port: the port where statsd is listening, defaults to 8125

        >>> from pystatsd import statsd
        >>> stats_client = statsd.Statsd(host, port)
        """
        self.host = host
        self.port = int(port)
        self.log = logging.getLogger("pystatsd.client")
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def timing(self, stat, time, sample_rate=1):
        """
        Log timing information for a single stat
        >>> from pystatsd import statsd
        >>> statsd_client.timing('some.time','500|ms')
        """
        stats = {stat: "%d|ms" % time}
        self.send(stats, sample_rate)

    def increment(self, stats, sample_rate=1):
        """
        Increments one or more stats counters
        >>> statsd_client.increment('some.int')
        >>> statsd_client.increment('some.int',0.5)
        """
        self.update_stats(stats, 1, sample_rate)

    def decrement(self, stats, sample_rate=1):
        """
        Decrements one or more stats counters
        >>> statsd_client.decrement('some.int')
        """
        self.update_stats(stats, -1, sample_rate)
    
    def update_stats(self, stats, delta=1, sampleRate=1):
        """
        Updates one or more stats counters by arbitrary amounts
        >>> statsd_client.update_stats('some.int',10)
        """
        if (type(stats) is not list):
            stats = [stats]
        data = {}
        for stat in stats:
            data[stat] = "%s|c" % delta

        self.send(data, sampleRate)
    
    def send(self, data, sample_rate=1):
        """
        Squirt the metrics over UDP
        """
        addr=(self.host, self.port)
        
        sampled_data = {}
        
        if(sample_rate < 1):
            if random.random() <= sample_rate:
                for stat, value in data.iteritems():
                    value = data[stat]
                    sampled_data[stat] = "%s|@%s" %(value, sample_rate)
        else:
            sampled_data=data
        
        try:
            for stat, value in sampled_data.iteritems():
                send_data = "%s:%s" % (stat, value)
                self.udp_sock.sendto(send_data, addr)
        except:
            self.log.exception("unexpected error")
            pass # we don't care
