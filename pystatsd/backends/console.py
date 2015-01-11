import logging

log = logging.getLogger(__name__)

class Console(object):
    def __init__(self, options={}):
        print("Console started")
        
    def init(self, cfg):
        self.debug           = cfg.get('debug')
        self.flush_interval  = cfg.get('flush_interval')
        
    def flush(self, timestamp, metrics):
        for k, v in metrics['counters'].items():
            print("%s => count=%s" % (k, v))
            
        for k, v in metrics['gauges'].items():
            print("%s => value=%s" % (k, v))
            
        for k, v in metrics['timers'].items():
            print("%s => lower=%s, mean=%s, upper=%s, %dpct=%s, count=%s"
                        % (k, v['min'], v['mean'], v['max'], v['pct_threshold'], v['max_threshold'], v['count']))
