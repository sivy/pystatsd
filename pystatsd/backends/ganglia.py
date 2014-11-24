import logging

from .. import gmetric

log = logging.getLogger(__name__)

class Ganglia(object):
    def init(self, options):
        self.ganglia_host   = options.get('ganglia_host', 'localhost')
        self.ganglia_port   = options.get('ganglia_port', 8649)
        self.ganglia_protocol = options.get('ganglia_protocol', 'udp')
        self.ganglia_spoof_host = options.get('ganglia_spoof_host', 'statsd:statsd')
        self.dmax = int(self.flush_interval * 1.2)
        self.debug           = options.get('debug')
        self.flush_interval  = options.get('flush_interval')
        
    def flush(self, timestamp, metrics):
        g = gmetric.Gmetric(self.ganglia_host, self.ganglia_port, self.ganglia_protocol)
        
        for k, v in metrics['counters'].items():
            # We put counters in _counters group. Underscore is to make sure counters show up
            # first in the GUI. Change below if you disagree
            g.send(k, v, "double", "count", "both", 60, self.dmax, "_counters", self.ganglia_spoof_host)
            
        for k, v in metrics['gauges'].items():
            g.send(k, v, "double", "count", "both", 60, self.dmax, "_gauges", self.ganglia_spoof_host)
            
        for k, v in metrics['timers'].items():
            # We are gonna convert all times into seconds, then let rrdtool 
            # add proper SI unit. This avoids things like 3521 k ms which 
            # is 3.521 seconds. What group should these metrics be in. For the 
            # time being we'll set it to the name of the key
            group = k
            g.send(k + "_min", min / 1000, "double", "seconds", "both", 60,
                   self.dmax, group, self.ganglia_spoof_host)
            g.send(k + "_mean", mean / 1000, "double", "seconds", "both", 60,
                   self.dmax, group, self.ganglia_spoof_host)
            g.send(k + "_max", max / 1000, "double", "seconds", "both", 60,
                   self.dmax, group, self.ganglia_spoof_host)
            g.send(k + "_count", count, "double", "count", "both", 60, self.dmax,
                   group, self.ganglia_spoof_host)
            g.send(k + "_" + str(self.pct_threshold) + "pct", max_threshold / 1000,
                   "double", "seconds", "both", 60, self.dmax, group, 
                   self.ganglia_spoof_host)
