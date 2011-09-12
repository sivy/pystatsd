import re
from socket import AF_INET, SOCK_DGRAM, socket
import threading
import time
import types
import logging

log = logging.getLogger(__name__)

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = None

from daemon import Daemon


__all__ = ['Server']

def _clean_key(k):
    return re.sub(
        r'[^a-zA-Z_\-0-9\.]',
        '',
        re.sub(
            r'\s+',
            '_',
            k.replace('/','-').replace(' ','_')
        )
    )

TIMER_MSG = '''%(prefix)s.%(key)s.lower %(min)s %(ts)s
%(prefix)s.%(key)s.count %(count)s %(ts)s
%(prefix)s.%(key)s.mean %(mean)s %(ts)s
%(prefix)s.%(key)s.upper %(max)s %(ts)s
%(prefix)s.%(key)s.upper_%(pct_threshold)s %(max_threshold)s %(ts)s
'''

class Server(object):
    
    def __init__(self, pct_threshold=90, debug=False, graphite_host='localhost', graphite_port=2003,
                 flush_interval=10000, no_aggregate_counters = False, counters_prefix = 'stats',
                 timers_prefix = 'stats.timers'):
        self.buf = 8192
        self.flush_interval = flush_interval
        self.pct_threshold = pct_threshold
        self.graphite_host = graphite_host
        self.graphite_port = graphite_port
        self.no_aggregate_counters = no_aggregate_counters
        self.counters_prefix = counters_prefix
        self.timers_prefix = timers_prefix
        self.debug = debug

        self.counters = {}
        self.timers = {}
        self.flusher = 0

    def process(self, data):
        bits = data.split(':')
        key = _clean_key(bits[0])

        del bits[0]
        if len(bits) == 0:
            bits.append(0)

        for bit in bits:
            sample_rate = 1;
            fields = bit.split('|')
            if None==fields[1]:
                log.error('Bad line: %s' % bit)
                return

            if (fields[1] == 'ms'):
                if key not in self.timers:
                    self.timers[key] = []
                self.timers[key].append(float(fields[0] or 0))
            else:
                if len(fields) == 3:
                    sample_rate = float(re.match('^@([\d\.]+)', fields[2]).groups()[0])
                if key not in self.counters:
                    self.counters[key] = 0;
                self.counters[key] += float(fields[0] or 1) * (1 / sample_rate)

    def flush(self):
        ts = int(time.time())
        stats = 0
        stat_string = ''
        for k, v in self.counters.items():
            v = float(v)
            v = v if self.no_aggregate_counters else v / (self.flush_interval / 1000)

            msg = '%s.%s %s %s\n' % (self.counters_prefix, k, v, ts)
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
                    thresh_index = int((self.pct_threshold / 100.0) * count)
                    max_threshold = v[thresh_index - 1]
                    total = sum(v[:thresh_index-1])
                    mean = total / thresh_index

                self.timers[k] = []

                stat_string += TIMER_MSG % {
                    'prefix':self.timers_prefix,
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

        stat_string += "statsd.numStats %s %d\n" % (stats, ts)

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

    def serve(self, hostname='', port=8125):
        assert type(port) is types.IntType, 'port is not an integer: %s' % (port)
        addr = (hostname, port)
        self._sock = socket(AF_INET, SOCK_DGRAM)
        self._sock.bind(addr)

        import signal
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


class ServerDaemon(Daemon):
    def run(self, options):
        if setproctitle:
            setproctitle('pystatsd')
        server = Server(pct_threshold = options.pct,
                        debug = options.debug,
                        graphite_host = options.graphite_host,
                        graphite_port = options.graphite_port,
                        flush_interval = options.flush_interval,
                        no_aggregate_counters = options.no_aggregate_counters,
                        counters_prefix = options.counters_prefix,
                        timers_prefix = options.timers_prefix)
        
        server.serve(options.name, options.port)

def run_server():
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug mode', default=False)
    parser.add_argument('-n', '--name', dest='name', help='hostname to run on ', default='')
    parser.add_argument('-p', '--port', dest='port', help='port to run on (default: 8125)', type=int, default=8125)
    parser.add_argument('--graphite-port', dest='graphite_port', help='port to connect to graphite on (default: 2003)', type=int, default=2003)
    parser.add_argument('--graphite-host', dest='graphite_host', help='host to connect to graphite on (default: localhost)', type=str, default='localhost')
    parser.add_argument('--flush-interval', dest='flush_interval', help='how often to send data to graphite in millis (default: 10000)', type=int, default=10000)
    parser.add_argument('--no-aggregate-counters', dest='no_aggregate_counters', help='should statsd report counters as absolute instead of count/sec', action='store_true')
    parser.add_argument('--counters-prefix', dest='counters_prefix', help='prefix to append before sending counter data to graphite (default: statsd)', type=str, default='statsd')
    parser.add_argument('--timers-prefix', dest='timers_prefix', help='prefix to append before sending timing data to graphite (default: statsd.timers)', type=str, default='statsd.timers')
    parser.add_argument('-t', '--pct', dest='pct', help='stats pct threshold (default: 90)', type=int, default=90)
    parser.add_argument('-D', '--daemon', dest='daemonize', action='store_true', help='daemonize', default=False)
    parser.add_argument('--pidfile', dest='pidfile', action='store', help='pid file', default='/tmp/pystatsd.pid')
    parser.add_argument('--restart', dest='restart', action='store_true', help='restart a running daemon', default=False)
    parser.add_argument('--stop', dest='stop', action='store_true', help='stop a running daemon', default=False)
    options = parser.parse_args(sys.argv[1:])

    daemon = ServerDaemon(options.pidfile)
    if options.daemonize:
        daemon.start(options)
    elif options.restart:
        daemon.restart(options)
    elif options.stop:
        daemon.stop()
    else:
        daemon.run(options)

if __name__ == '__main__':
    run_server()