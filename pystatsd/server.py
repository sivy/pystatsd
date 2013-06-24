import re
import socket
import threading
import time
import types
import logging
import gmetric
from subprocess import call
from warnings import warn
# from xdrlib import Packer, Unpacker

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
            k.replace('/', '-').replace(' ', '_')
        )
    )



TIMER_MSG = '''%(prefix)s.%(key)s.lower %(min)s %(ts)s
%(prefix)s.%(key)s.count %(count)s %(ts)s
%(prefix)s.%(key)s.mean %(mean)s %(ts)s
%(prefix)s.%(key)s.upper %(max)s %(ts)s
%(prefix)s.%(key)s.upper_%(pct_threshold)s %(max_threshold)s %(ts)s
'''


class Server(object):

    def __init__(self, pct_threshold=90, debug=False, transport='graphite',
                 ganglia_host='localhost', ganglia_port=8649,
                 ganglia_spoof_host='statsd:statsd',
                 gmetric_exec='/usr/bin/gmetric', gmetric_options = '-d',
                 graphite_host='localhost', graphite_port=2003, flush_interval=10000,
                 no_aggregate_counters=False, counters_prefix='stats',
                 timers_prefix='stats.timers', expire=0):
        self.buf = 8192
        self.flush_interval = flush_interval
        self.pct_threshold = pct_threshold
        self.transport = transport
        # Embedded Ganglia library options specific settings
        self.ganglia_host = ganglia_host
        self.ganglia_port = ganglia_port
        self.ganglia_protocol = "udp"
        # Use gmetric
        self.gmetric_exec = gmetric_exec
        self.gmetric_options = gmetric_options
        # Set DMAX to flush interval plus 20%. That should avoid metrics to prematurely expire if there is
        # some type of a delay when flushing
        self.dmax = int(self.flush_interval * 1.2)
        # What hostname should these metrics be attached to.
        self.ganglia_spoof_host = ganglia_spoof_host

        # Graphite specific settings
        self.graphite_host = graphite_host
        self.graphite_port = graphite_port
        self.no_aggregate_counters = no_aggregate_counters
        self.counters_prefix = counters_prefix
        self.timers_prefix = timers_prefix
        self.debug = debug
        self.expire = expire

        self.counters = {}
        self.timers = {}
        self.gauges = {}
        self.flusher = 0

    def send_to_ganglia_using_gmetric(self,k,v,group, units):
        call([self.gmetric_exec, self.gmetric_options, "-u", units, "-g", group, "-t", "double", "-n",  k, "-v", str(v) ])    

    def process(self, data):
        data.rstrip('\n')

        for metric in data.split('\n'):
            bits = metric.split(':')
            key = _clean_key(bits[0])
            ts = int(time.time())

            del bits[0]
            if len(bits) == 0:
                bits.append(0)

            for bit in bits:
                sample_rate = 1
                fields = bit.split('|')
                if None == fields[1]:
                    log.error('Bad line: %s' % bit)
                    return

                if (fields[1] == 'ms'):
                    if key not in self.timers:
                        self.timers[key] = [ [], ts ]
                    self.timers[key][0].append(float(fields[0] or 0))
                    self.timers[key][1] = ts
                elif (fields[1] == 'g'):
                    self.gauges[key] = [ float(fields[0]), ts ]
                elif (fields[1] == 'c'):
                    if len(fields) == 3:
                        sample_rate = float(re.match('^@([\d\.]+)', fields[2]).groups()[0])
                    if key not in self.counters:
                        self.counters[key] = [ 0, ts ]
                    self.counters[key][0] += float(fields[0] or 1) * (1 / sample_rate)
                    self.counters[key][1] = ts
                else:
                    warn("Encountered unknown metric type %s in <%s>"
                        % (fields[1], metric))

    def flush(self):
        ts = int(time.time())
        stats = 0

        if self.transport == 'graphite':
            stat_string = ''
        elif self.transport == 'ganglia':
            g = gmetric.Gmetric(self.ganglia_host, self.ganglia_port, self.ganglia_protocol)

        for k, (v, t) in self.counters.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    print "Expiring counter %s (age: %s)" % (k, ts -t)
                del(self.counters[k])
                continue
            v = float(v)
            v = v if self.no_aggregate_counters else v / (self.flush_interval / 1000)

            if self.debug:
                print "Sending %s => count=%s" % (k, v)

            if self.transport == 'graphite':
                msg = '%s.%s %s %s\n' % (self.counters_prefix, k, v, ts)
                stat_string += msg
            elif self.transport == 'ganglia':
                # We put counters in _counters group. Underscore is to make sure counters show up
                # first in the GUI. Change below if you disagree
                g.send(k, v, "double", "count", "both", 60, self.dmax, "_counters", self.ganglia_spoof_host)
            elif self.transport == 'ganglia-gmetric':
                self.send_to_ganglia_using_gmetric(k,v, "_counters", "count")

            # Zero out the counters once the data is sent
            self.counters[k] = [0, int(time.time())]
            stats += 1

        for k, (v, t) in self.gauges.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    print "Expiring gauge %s (age: %s)" % (k, ts - t)
                del(self.gauges[k])
                continue
            v = float(v)

            if self.debug:
                print "Sending %s => count=%s" % (k, v)

            if self.transport == 'graphite':
                # note: counters and gauges implicitly end up in the same namespace
                msg = '%s.%s %s %s\n' % (self.counters_prefix, k, v, ts)
                stat_string += msg
            elif self.transport == 'ganglia':
                g.send(k, v, "double", "count", "both", 60, self.dmax, "_gauges", self.ganglia_spoof_host)
            elif self.transport == 'ganglia-gmetric':
                self.send_to_ganglia_using_gmetric(k,v, "_gauges", "gauge")

            stats += 1

        for k, (v, t) in self.timers.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    print "Expiring timer %s (age: %s)" % (k, ts - t)
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

                del(self.timers[k])

                if self.debug:
                    print "Sending %s ====> lower=%s, mean=%s, upper=%s, %dpct=%s, count=%s" \
                        % (k, min, mean, max, self.pct_threshold, max_threshold, count)

                if self.transport == 'graphite':

                    stat_string += TIMER_MSG % {
                        'prefix': self.timers_prefix,
                        'key': k,
                        'mean': mean,
                        'max': max,
                        'min': min,
                        'count': count,
                        'max_threshold': max_threshold,
                        'pct_threshold': self.pct_threshold,
                        'ts': ts,
                    }

                elif self.transport == 'ganglia':
                    # We are gonna convert all times into seconds, then let rrdtool add proper SI unit. This avoids things like
                    # 3521 k ms which is 3.521 seconds
                    # What group should these metrics be in. For the time being we'll set it to the name of the key
                    group = k
                    g.send(k + "_min", min / 1000, "double", "seconds", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                    g.send(k + "_mean", mean / 1000, "double", "seconds", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                    g.send(k + "_max", max / 1000, "double", "seconds", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                    g.send(k + "_count", count, "double", "count", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                    g.send(k + "_" + str(self.pct_threshold) + "pct", max_threshold / 1000, "double", "seconds", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                elif self.transport == 'ganglia-gmetric':
                    # We are gonna convert all times into seconds, then let rrdtool add proper SI unit. This avoids things like
                    # 3521 k ms which is 3.521 seconds
                    group = k
                    self.send_to_ganglia_using_gmetric(k + "_mean", mean / 1000, group, "seconds")
                    self.send_to_ganglia_using_gmetric(k + "_min",  min / 1000 , group, "seconds")
                    self.send_to_ganglia_using_gmetric(k + "_max",  max / 1000, group, "seconds")
                    self.send_to_ganglia_using_gmetric(k + "_count", count , group, "count")
                    self.send_to_ganglia_using_gmetric(k + "_" + str(self.pct_threshold) + "pct",  max_threshold / 1000, group, "seconds")

                stats += 1

        if self.transport == 'graphite':

            stat_string += "statsd.numStats %s %d\n" % (stats, ts)
            graphite = socket.socket()
            try:
                graphite.connect((self.graphite_host, self.graphite_port))
                graphite.sendall(stat_string)
                graphite.close()
            except socket.error, e:
                log.error("Error communicating with Graphite: %s" % e)
                if self.debug:
                    print "Error communicating with Graphite: %s" % e

        self._set_timer()

        if self.debug:
            print "\n================== Flush completed. Waiting until next flush. Sent out %d metrics =======" \
                % (stats)

    def _set_timer(self):
        self._timer = threading.Timer(self.flush_interval / 1000, self.flush)
        self._timer.start()

    def serve(self, hostname='', port=8125):
        assert type(port) is types.IntType, 'port is not an integer: %s' % (port)
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
            self.process(data)

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
    parser.add_argument('--counters-prefix', dest='counters_prefix', help='prefix to append before sending counter data to graphite (default: stats)', type=str, default='stats')
    parser.add_argument('--timers-prefix', dest='timers_prefix', help='prefix to append before sending timing data to graphite (default: stats.timers)', type=str, default='stats.timers')
    parser.add_argument('-t', '--pct', dest='pct', help='stats pct threshold (default: 90)', type=int, default=90)
    parser.add_argument('-D', '--daemon', dest='daemonize', action='store_true', help='daemonize', default=False)
    parser.add_argument('--pidfile', dest='pidfile', action='store', help='pid file', default='/var/run/pystatsd.pid')
    parser.add_argument('--restart', dest='restart', action='store_true', help='restart a running daemon', default=False)
    parser.add_argument('--stop', dest='stop', action='store_true', help='stop a running daemon', default=False)
    parser.add_argument('--expire', dest='expire', help='time-to-live for old stats (in secs)', type=int, default=0)
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
