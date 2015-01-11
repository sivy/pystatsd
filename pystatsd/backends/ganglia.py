import logging

from .. import gmetric

log = logging.getLogger(__name__)

class Ganglia(object):
    def __init__(self, options):
        self.host       = options.get('ganglia_host', 'localhost')
        self.port       = options.get('ganglia_port', 8649)
        self.protocol   = options.get('ganglia_protocol', 'udp')
        self.spoof_host = options.get('ganglia_spoof_host', 'statsd:statsd')
        
    def init(self, options):
        self.debug           = options.get('debug')
        self.flush_interval  = options.get('flush_interval')
        self.dmax            = int(self.flush_interval * 1.2)
        
    def flush(self, timestamp, metrics):
        g = gmetric.Gmetric(self.host, self.port, self.protocol)
        
        for k, v in metrics['counters'].items():
            # We put counters in _counters group. Underscore is to make sure counters show up
            # first in the GUI. Change below if you disagree
            g.send(k, v, "double", "count", "both", 60, self.dmax, "_counters", self.spoof_host)
            
        for k, v in metrics['gauges'].items():
            g.send(k, v, "double", "count", "both", 60, self.dmax, "_gauges", self.spoof_host)
            
        for k, v in metrics['timers'].items():
            # We are gonna convert all times into seconds, then let rrdtool 
            # add proper SI unit. This avoids things like 3521 k ms which 
            # is 3.521 seconds. What group should these metrics be in. For the 
            # time being we'll set it to the name of the key
            group = k
            g.send(k + "_min", v['min'] / 1000, "double", "seconds", "both", 60,
                   self.dmax, group, self.spoof_host)
            g.send(k + "_mean", v['mean'] / 1000, "double", "seconds", "both", 60,
                   self.dmax, group, self.spoof_host)
            g.send(k + "_max", v['max'] / 1000, "double", "seconds", "both", 60,
                   self.dmax, group, self.spoof_host)
            g.send(k + "_count", v['count'], "double", "count", "both", 60, self.dmax,
                   group, self.spoof_host)
            g.send(k + "_" + str(v['pct_threshold']) + "pct", v['max_threshold'] / 1000,
                   "double", "seconds", "both", 60, self.dmax, group, 
                   self.spoof_host)
