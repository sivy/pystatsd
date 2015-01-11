import logging

from subprocess import call
from .ganglia import Ganglia

log = logging.getLogger(__name__)

class Gmetric(object):
    def __init__(self, options):
        self.gmetric_exec    = options.get('gmetric_exec', '/usr/bin/gmetric')
        self.gmetric_options = options.get('gmetric_options', '-d')
        
    def init(self, options):
        self.debug           = options.get('debug')
        self.flush_interval  = options.get('flush_interval')
        
    def flush(self, timestamp, metrics):
        for k, v in metrics['counters'].items():
            self.send(k, v, "_counters", "count")
            
        for k, v in metrics['gauges'].items():
            self.send(k, v, "_gauges", "gauge")
            
        for k, v in metrics['timers'].items():
            # We are gonna convert all times into seconds, then let rrdtool add proper SI unit. This avoids things like
            # 3521 k ms which is 3.521 seconds
            group = k
            self.send(k + "_mean", v['mean'] / 1000, group, "seconds")
            self.send(k + "_min",  v['min'] / 1000 , group, "seconds")
            self.send(k + "_max",  v['max'] / 1000, group, "seconds")
            self.send(k + "_count", v['count'] , group, "count")
            self.send(k + "_" + str(v['pct_threshold']) + "pct", v['max_threshold'] / 1000, group, "seconds")
                   
    def send(self, k, v, group, units):
        call([self.gmetric_exec, self.gmetric_options, "-u", units, "-g", group, "-t", "double", "-n",  k, "-v", str(v) ])
