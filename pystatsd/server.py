import re
import socket
import threading
import time
import types
import logging
from . import gmetric
from subprocess import call
from warnings import warn
# from xdrlib import Packer, Unpacker

log = logging.getLogger(__name__)

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = None

from .daemon import Daemon


__all__ = ['Server']


def _clean_key(k):
    return re.sub(
        r'[^a-zA-Z_\-0-9\.]',
        '',
        re.sub(
            r'\s+',
            '_',
            k.replace('/', '-').replace(' ', '_')
        )
    )
    

class Server(object):

    def __init__(self, pct_threshold=90, debug=False, transport='graphite',
                 flush_interval=10000, expire=0, no_aggregate_counters=False,
                 deleteGauges=False, backends=[], options={}):
        self.buf = 8192
        self.flush_interval = flush_interval
        self.pct_threshold = pct_threshold
        self.transport = transport

        self.no_aggregate_counters = no_aggregate_counters
        self.debug = debug
        self.expire = expire

        self.backends = backends
        self.deleteGauges = deleteGauges
        
        options.update({'debug': debug, 'flush_interval': flush_interval})
        for backend in backends:
            backend.init(options)
        
        self.counters = {}
        self.timers = {}
        self.gauges = {}
        self.flusher = 0

    def process(self, data):
        # the data is a sequence of newline-delimited metrics
        # a metric is in the form "name:value|rest"  (rest may have more pipes)
        data.rstrip('\n')

        for metric in data.split('\n'):
            match = re.match('\A([^:]+):([^|]+)\|(.+)', metric)

            if match == None:
                warn("Skipping malformed metric: <%s>" % (metric))
                continue

            key   = _clean_key( match.group(1) )
            value = match.group(2)
            rest  = match.group(3).split('|')
            mtype = rest.pop(0)

            if   (mtype == 'ms'): self.__record_timer(key, value, rest)
            elif (mtype == 'g' ): self.__record_gauge(key, value, rest)
            elif (mtype == 'c' ): self.__record_counter(key, value, rest)
            else:
                warn("Encountered unknown metric type in <%s>" % (metric))

    def __record_timer(self, key, value, rest):
        ts = int(time.time())
        timer = self.timers.setdefault(key, [ [], ts ])
        timer[0].append(float(value or 0))
        timer[1] = ts

    def __record_gauge(self, key, value, rest):
        ts = int(time.time())
        self.gauges[key] = [ float(value), ts ]

    def __record_counter(self, key, value, rest):
        ts = int(time.time())
        sample_rate = 1.0
        if len(rest) == 1:
            sample_rate = float(re.match('^@([\d\.]+)', rest[0]).group(1))
            if sample_rate == 0:
                warn("Ignoring counter with sample rate of zero: <%s>" % (metric))
                return

        counter = self.counters.setdefault(key, [ 0, ts ])
        counter[0] += float(value or 1) * (1 / sample_rate)
        counter[1] = ts

    def on_timer(self):
        """Executes flush(). Ignores any errors to make sure one exception
        doesn't halt the whole flushing process.
        """
        try:
            self.flush()
        except Exception as e:
            print e
            log.exception('Error while flushing: %s', e)
        self._set_timer()

    def flush(self):
        ts = int(time.time())
        stats = 0
        metrics = {'counters': {}, 'gauges': {}, 'timers': {}}
        
        for k, (v, t) in self.counters.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    print("Expiring counter %s (age: %s)" % (k, ts -t))
                del(self.counters[k])
                continue
            v = float(v)
            v = v if self.no_aggregate_counters else v / (self.flush_interval / 1000)
            metrics['counters'][k] = v

            # Clear the counter once the data is sent
            del(self.counters[k])
            stats += 1
                
        for k, (v, t) in self.gauges.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    print("Expiring gauge %s (age: %s)" % (k, ts - t))
                del(self.gauges[k])
                continue
            metrics['gauges'][k] = float(v)
            if self.deleteGauges:
                del(self.gauges[k])
            stats += 1
            
        for k, (v, t) in self.timers.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    print("Expiring timer %s (age: %s)" % (k, ts - t))
                del(self.timers[k])
                continue
            if len(v) > 0:
                # Sort all the received values. We need it to extract percentiles
                v.sort()
                count = len(v)
                min = v[0]
                max = v[-1]

                mean = min
                max_threshold = max

                if count > 1:
                    thresh_index = int((self.pct_threshold / 100.0) * count)
                    max_threshold = v[thresh_index - 1]
                    total = sum(v)
                    mean = total / count

                metrics['timers'][k] = {
                    'mean': mean, 'max': max, 'min': min, 'count': count,
                    'max_threshold': max_threshold, 'pct_threshold': pct_threshold
                }
                del(self.timers[k])
                stats += 1
                
        for backend in self.backends:
            backend.flush(ts, metrics)
            
        if self.debug:
            print("\n================== Flush completed. Waiting until next flush. Sent out %d metrics =======" \
                % (stats))

    def _set_timer(self):
        self._timer = threading.Timer(self.flush_interval / 1000, self.on_timer)
        self._timer.daemon = True
        self._timer.start()

    def serve(self, hostname='', port=8125):
        assert type(port) is int, 'port is not an integer: %s' % (port)
        addr = (hostname, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(addr)

        import signal

        def signal_handler(signal, frame):
                self.stop()
        signal.signal(signal.SIGINT, signal_handler)

        self._set_timer()
        while 1:
            data, addr = self._sock.recvfrom(self.buf)
            try:
                self.process(data)
            except Exception as error:
                log.error("Bad data from %s: %s",addr,error) 


    def stop(self):
        self._timer.cancel()
        self._sock.close()


class ServerDaemon(Daemon):
    def run(self, options):
        if setproctitle:
            setproctitle('pystatsd')
        server = Server(pct_threshold=options.pct,
                        debug=options.debug,
                        transport=options.transport,
                        graphite_host=options.graphite_host,
                        graphite_port=options.graphite_port,
                        global_prefix=options.global_prefix,
                        ganglia_host=options.ganglia_host,
                        ganglia_spoof_host=options.ganglia_spoof_host,
                        ganglia_port=options.ganglia_port,
                        gmetric_exec=options.gmetric_exec,
                        gmetric_options=options.gmetric_options,
                        flush_interval=options.flush_interval,
                        no_aggregate_counters=options.no_aggregate_counters,
                        counters_prefix=options.counters_prefix,
                        timers_prefix=options.timers_prefix,
                        expire=options.expire)

        server.serve(options.name, options.port)


def run_server():
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug mode', default=False)
    parser.add_argument('-n', '--name', dest='name', help='hostname to run on ', default='')
    parser.add_argument('-p', '--port', dest='port', help='port to run on (default: 8125)', type=int, default=8125)
    parser.add_argument('-r', '--transport', dest='transport', help='transport to use graphite, ganglia (uses embedded library) or ganglia-gmetric (uses gmetric)', type=str, default="graphite")
    parser.add_argument('--graphite-port', dest='graphite_port', help='port to connect to graphite on (default: 2003)', type=int, default=2003)
    parser.add_argument('--graphite-host', dest='graphite_host', help='host to connect to graphite on (default: localhost)', type=str, default='localhost')
    # Uses embedded Ganglia Library
    parser.add_argument('--ganglia-port', dest='ganglia_port', help='Unicast port to connect to ganglia on', type=int, default=8649)
    parser.add_argument('--ganglia-host', dest='ganglia_host', help='Unicast host to connect to ganglia on', type=str, default='localhost')
    parser.add_argument('--ganglia-spoof-host', dest='ganglia_spoof_host', help='host to report metrics as to ganglia', type=str, default='statsd:statsd')
    # Use gmetric
    parser.add_argument('--ganglia-gmetric-exec', dest='gmetric_exec', help='Use gmetric executable. Defaults to /usr/bin/gmetric', type=str, default="/usr/bin/gmetric")
    parser.add_argument('--ganglia-gmetric-options', dest='gmetric_options', help='Options to pass to gmetric. Defaults to -d 60', type=str, default="-d 60")
    # 
    parser.add_argument('--flush-interval', dest='flush_interval', help='how often to send data to graphite in millis (default: 10000)', type=int, default=10000)
    parser.add_argument('--no-aggregate-counters', dest='no_aggregate_counters', help='should statsd report counters as absolute instead of count/sec', action='store_true')
    parser.add_argument('--global-prefix', dest='global_prefix', help='prefix to append to all stats sent to graphite. Useful for hosted services (ex: Hosted Graphite) or stats namespacing (default: None)', type=str, default=None)
    parser.add_argument('--counters-prefix', dest='counters_prefix', help='prefix to append before sending counter data to graphite (default: stats)', type=str, default='stats')
    parser.add_argument('--timers-prefix', dest='timers_prefix', help='prefix to append before sending timing data to graphite (default: stats.timers)', type=str, default='stats.timers')
    parser.add_argument('-t', '--pct', dest='pct', help='stats pct threshold (default: 90)', type=int, default=90)
    parser.add_argument('-D', '--daemon', dest='daemonize', action='store_true', help='daemonize', default=False)
    parser.add_argument('--pidfile', dest='pidfile', action='store', help='pid file', default='/var/run/pystatsd.pid')
    parser.add_argument('--restart', dest='restart', action='store_true', help='restart a running daemon', default=False)
    parser.add_argument('--stop', dest='stop', action='store_true', help='stop a running daemon', default=False)
    parser.add_argument('--expire', dest='expire', help='time-to-live for old stats (in secs)', type=int, default=0)
    options = parser.parse_args(sys.argv[1:])

    log_level = logging.DEBUG if options.debug else logging.INFO
    logging.basicConfig(level=log_level,format='%(asctime)s [%(levelname)s] %(message)s')

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
