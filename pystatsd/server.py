import types
import re
import time

import threading
from socket import AF_INET, SOCK_DGRAM, socket

__all__ = ['Server']

def _clean_key(k):
    return re.sub(
        '[^a-zA-Z_\-0-9\.]',
        '',
        k.replace('/','-').replace(' ','_')
    )


TIMER_MSG = '''stats.timers.%(key)s.lower %(min)s %(ts)s
stats.timers.%(key)s.count %(count)s %(ts)s
stats.timers.%(key)s.mean %(mean)s %(ts)s
stats.timers.%(key)s.upper %(max)s %(ts)s
stats.timers.%(key)s.upper_%(pct_threshold)s %(max_threshold)s %(ts)s
'''

class Server(object):

    def __init__(self, pct_threshold=90, debug=False, graphite_host='localhost', graphite_port=2003):
        self.buf = 1024
        self.flush_interval = 10000
        self.pct_threshold = pct_threshold
        self.graphite_host = graphite_host
        self.graphite_port = graphite_port
        self.debug = debug

        self.counters = {}
        self.timers = {}
        self.flusher = 0

    
    def process(self, data):
        key, val = data.split(':')
        key = _clean_key(key)

        sample_rate = 1;
        fields = val.split('|')

        if (fields[1] == 'ms'):
            if key not in self.timers:
                self.timers[key] = []
            self.timers[key].append(int(fields[0] or 0))
        else:
            if len(fields) == 3:
                sample_rate = float(re.match('^@([\d\.]+)', fields[2]).groups()[0])
            if key not in self.counters:
                self.counters[key] = 0;
            self.counters[key] += int(fields[0] or 1) * (1 / sample_rate)
        
    def flush(self):
        ts = int(time.time())
        stats = 0
        stat_string = ''
        self.pct_threshold = 10
        for k, v in self.counters.items():
            v = float(v) / (self.flush_interval / 1000)
            msg = 'stats.%s %s %s\n' % (k, v, ts)
            stat_string += msg

            self.counters[k] = 0
            stats += 1

        for k, v in self.timers.items():
            if len(v) > 0:
                v.sort()
                count = len(v)
                min = v[0]
                max = v[-1]

                mean = min
                max_threshold = max

                if count > 1:
                    thresh_index = int(((100.0 - self.pct_threshold) / 100) * count)
                    max_threshold = v[thresh_index - 1]
                    total = sum(v[:thresh_index-1])
                    mean = total / thresh_index

                self.timers[k] = []

                stat_string += TIMER_MSG % {
                    'key':k,
                    'mean':mean,
                    'max': max,
                    'min': min,
                    'count': count,
                    'max_threshold': max_threshold,
                    'pct_threshold': self.pct_threshold,
                    'ts': ts,
                }
                stats += 1
        
        stat_string += 'statsd.numStats %s %d' % (stats, ts)

        graphite = socket()
        graphite.connect((self.graphite_host, self.graphite_port))
        graphite.sendall(stat_string)
        graphite.close()
        self._set_timer()

        if self.debug:
            print stat_string


    def _set_timer(self):
        self._timer = threading.Timer(self.flush_interval/1000, self.flush)
        self._timer.start()

    def serve(self, hostname='', port=8125, graphite_host='localhost', graphite_port=2003):
        assert type(port) is types.IntType, 'port is not an integer: %s' % (port)
        addr = (hostname, port)
        self._sock = socket(AF_INET, SOCK_DGRAM)
        self._sock.bind(addr)
        self.graphite_host = graphite_host
        self.graphite_port = graphite_port

        import signal
        import sys
        def signal_handler(signal, frame):
                self.stop()
        signal.signal(signal.SIGINT, signal_handler)
        
        self._set_timer()
        while 1:
            data, addr = self._sock.recvfrom(self.buf)
            self.process(data)

    def stop(self):
        self._timer.cancel()
        self._sock.close()
        

if __name__ == '__main__':
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug mode', default=False)
    parser.add_argument('-n', '--name', dest='name', help='hostname to run on', default='')
    parser.add_argument('-p', '--port', dest='port', help='port to run on', type=int, default=8125)
    parser.add_argument('--graphite-port', dest='graphite_port', help='port to connect to graphite on', type=int, default=2003)
    parser.add_argument('--graphite-host', dest='graphite_host', help='host to connect to graphite on', type=str, default='localhost')
    parser.add_argument('-t', '--pct', dest='pct', help='stats pct threshold', type=int, default=90)
    options = parser.parse_args(sys.argv[1:])

    Server(pct_threshold=options.pct, debug=options.debug).serve(options.name, options.port, options.graphite_host, options.graphite_port)
