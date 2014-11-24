import logging

log = logging.getLogger(__name__)

class Console(object):
    def init(self, options):
        self.debug           = options.get('debug')
        self.flush_interval  = options.get('flush_interval')
        
    def flush(self, timestamp, metrics):
        for k, v in metrics['counters'].items():
            print("%s => count=%s" % (k, v))
            
        for k, v in metrics['gauges'].items():
            print("%s => value=%s" % (k, v))
            
        for k, v in metrics['timers'].items():
            print("%s => lower=%s, mean=%s, upper=%s, %dpct=%s, count=%s"
                        % (k, v['min'], v['mean'], v['max'], v['pct_threshold'], v['max_threshold'], v['count']))
