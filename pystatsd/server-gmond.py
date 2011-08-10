import re
from socket import AF_INET, SOCK_DGRAM, socket
import threading
import time
import types
import gmetric
from xdrlib import Packer, Unpacker

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = None

from daemon import Daemon


__all__ = ['Server']

def _clean_key(k):
    return re.sub(
        '[^a-zA-Z_\-0-9\.]',
        '',
        k.replace('/','-').replace(' ','_')
    )

class Server(object):

    def __init__(self, pct_threshold=90, debug=False, ganglia_host='localhost', ganglia_port=8649):
        self.buf = 1024
        # How often to flush metrics in milliseconds (default 15 seconds)
        self.flush_interval = 15000
        # Set DMAX to flush interval plus 20%. That should avoid metrics to prematurely expire if there is
        # some type of a delay when flushing
        self.dmax = int ( self.flush_interval * 1.2 ) 
        self.pct_threshold = pct_threshold
        self.ganglia_host = ganglia_host
        self.ganglia_port = ganglia_port
        self.ganglia_protocol = "udp"
        self.debug = debug
        # What hostname should these metrics be attached to. Here we'll just create a fake host called
        # statsd
        self.ganglia_spoof_host = "statsd:statsd"

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
        stats = 0
        g = gmetric.Gmetric(self.ganglia_host, self.ganglia_port, self.ganglia_protocol)

        for k, v in self.counters.items():
            v = float(v) / (self.flush_interval / 1000)
            if self.debug:
                print "Sending %s => count=%s" % ( k, v )
            # We put counters in _counters group. Underscore is to make sure counters show up
            # first in the GUI. Change below if you disagree
            g.send(k, v, "double", "count", "both", 60, self.dmax, "_counters", self.ganglia_spoof_host)

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
                    mean = total / count

                self.timers[k] = []

                if self.debug:
                    print "Sending %s ====> lower=%s, mean=%s, upper=%s, %dpct=%s, count=%s" % ( k, min, mean, max, self.pct_threshold, max_threshold, count )
                # What group should these metrics be in. For the time being we'll set it to the name of the key
                group = k
                g.send(k + "_lower", min, "double", "time", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                g.send(k + "_mean", mean, "double", "time", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                g.send(k + "_upper", max, "double", "time", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                g.send(k + "_count", count, "double", "count", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                g.send(k + "_" + str(self.pct_threshold) +"pct", max_threshold, "double", "time", "both", 60, self.dmax, group, self.ganglia_spoof_host)
                
                stats += 1

        if self.debug:
            print "\n================== Flush completed. Waiting until next flush. Sent out %d metrics =======" % ( stats )


        self._set_timer()

    def _set_timer(self):
        self._timer = threading.Timer(self.flush_interval/1000, self.flush)
        self._timer.start()

    def serve(self, hostname='', port=8125, ganglia_host='localhost', ganglia_port=8649):
        assert type(port) is types.IntType, 'port is not an integer: %s' % (port)
        addr = (hostname, port)
        self._sock = socket(AF_INET, SOCK_DGRAM)
        self._sock.bind(addr)
        self.ganglia_host = ganglia_host
        self.ganglia_port = ganglia_port

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

class ServerDaemon(Daemon):
    def run(self, options):
        if setproctitle:
            setproctitle('pystatsd')
        server = Server(pct_threshold=options.pct, debug=options.debug)
        server.serve(options.name, options.port, options.ganglia_host,
                     options.ganglia_port)

def run_server():
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug mode', default=False)
    parser.add_argument('-n', '--name', dest='name', help='hostname to run on', default='')
    parser.add_argument('-p', '--port', dest='port', help='port to run on', type=int, default=8125)
    parser.add_argument('--ganglia-port', dest='ganglia_port', help='port to connect to ganglia on', type=int, default=8649)
    parser.add_argument('--ganglia-host', dest='ganglia_host', help='host to connect to ganglia on', type=str, default='localhost')
    parser.add_argument('-t', '--pct', dest='pct', help='stats pct threshold', type=int, default=90)
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