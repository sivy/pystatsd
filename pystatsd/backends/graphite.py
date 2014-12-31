import socket
import logging


TIMER_MSG = '''%(prefix)s.%(key)s.lower %(min)s %(ts)s
%(prefix)s.%(key)s.count %(count)s %(ts)s
%(prefix)s.%(key)s.mean %(mean)s %(ts)s
%(prefix)s.%(key)s.upper %(max)s %(ts)s
%(prefix)s.%(key)s.upper_%(pct_threshold)s %(max_threshold)s %(ts)s
'''

log = logging.getLogger(__name__)

class Graphite(object):
    def __init__(self, options={}):
        self.host            = options.get('graphite_host', 'localhost')
        self.port            = options.get('graphite_port', 2003)
        self.counters_prefix = options.get('counters_prefix', 'stats')
        self.timers_prefix   = options.get('timers_prefix', 'stats.timers')
        self.global_prefix   = options.get('global_prefix', None)
    
    def init(self, cfg):
        self.debug           = cfg.get('debug')
        self.flush_interval  = cfg.get('flush_interval')
        
    def flush(self, timestamp, metrics):
        stat_string = ''
        stats = 0
        
        for k, v in metrics['counters'].items():
            msg = '%s.%s %s %s\n' % (self.counters_prefix, k, v, timestamp)
            stat_string += msg
            stats += 1
            
        for k, v in metrics['gauges'].items():
            msg = '%s.%s %s %s\n' % (self.counters_prefix, k, v, timestamp)
            stat_string += msg
            stats += 1
            
        for k, v in metrics['timers'].items():
            v.update({'prefix': self.timers_prefix, 'key': k, 'ts': timestamp})
            stat_string += TIMER_MSG % v
            stats += 1
             
        stat_string += "statsd.numStats %s %d\n" % (stats, timestamp)
        self._send_metrics(stat_string)

    def _send_metrics(self, stat_string):
        # Prepend stats with Hosted Graphite API key if necessary
        if self.global_prefix:
            stat_string = '\n'.join([
                '%s.%s' % (self.global_prefix, s) for s in stat_string.split('\n')[:-1]
            ])

        graphite = socket.socket()
        
        try:
            graphite.connect((self.host, self.port))
            graphite.sendall(bytes(bytearray(stat_string, "utf-8")))
            graphite.close()
        except socket.error as e:
            log.error("Error communicating with Graphite: %s" % e)
            if self.debug:
                print("Error communicating with Graphite: %s" % e)
