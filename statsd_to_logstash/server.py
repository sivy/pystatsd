import re
import socket
import threading
import time
import logging
import logstash

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = None

try:
    from .daemon import Daemon
except ValueError:
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


class Server(object):

    def __init__(self, pct_threshold=90, debug=False,
                 flush_interval=10000,
                 no_aggregate_counters=False,
                 expire=0, metadata=None):

        if metadata is None:
            metadata = dict()

        self.buf = 8192
        self.flush_interval = flush_interval
        self.pct_threshold = pct_threshold

        self.no_aggregate_counters = no_aggregate_counters
        self.debug = debug
        self.expire = expire

        self.counters = {}
        self.timers = {}
        self.gauges = {}

        self.metadata = metadata

    def process(self, data):
        # the data is a sequence of newline-delimited metrics
        # a metric is in the form "name:value|rest"  (rest may have more pipes)
        data.rstrip('\n')

        for metric in data.split('\n'):
            match = re.match('\A([^:]+):([^|]+)\|(.+)', metric)

            if match is None:
                debug_log.warning(
                    "Skipping malformed metric: <%s>" % (metric))

                continue

            key = _clean_key(match.group(1))
            value = match.group(2)
            rest = match.group(3).split('|')
            mtype = rest.pop(0)

            if (mtype == 'ms'):
                self.__record_timer(key, value, rest)
            elif (mtype == 'g'):
                self.__record_gauge(key, value, rest)
            elif (mtype == 'c'):
                self.__record_counter(key, value, rest)
            else:
                debug_log.warning(
                    "Encountered unknown metric type in <%s>" % (metric))

    def __record_timer(self, key, value, rest):
        ts = int(time.time())
        timer = self.timers.setdefault(key, [[], ts])
        timer[0].append(float(value or 0))
        timer[1] = ts

    def __record_gauge(self, key, value, rest):
        ts = int(time.time())
        self.gauges[key] = [float(value), ts]

    def __record_counter(self, key, value, rest):
        ts = int(time.time())
        sample_rate = 1.0

        if len(rest) == 1:
            sample_rate = float(re.match('^@([\d\.]+)', rest[0]).group(1))

            if sample_rate == 0:
                debug_log.warning(
                    "Ignoring counter with sample rate of zero: <%s>" % (key))

                return

        counter = self.counters.setdefault(key, [0, ts])
        counter[0] += float(value or 1) * (1 / sample_rate)
        counter[1] = ts

    def on_timer(self):
        """Executes flush(). Ignores any errors to make sure one exception
        doesn't halt the whole flushing process.
        """
        try:
            self.flush()
        except Exception as e:
            debug_log.exception('Error while flushing: %s', e)
        self._set_timer()

    def __flush_counters(self, stats, ts):
        for k, (v, t) in self.counters.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    debug_log.debug("Expiring counter %s (age: %s)" % (
                        k, ts - t))
                del(self.counters[k])

                continue
            v = float(v)
            v = v if self.no_aggregate_counters else v / (
                self.flush_interval / 1000)

            if self.debug:
                debug_log.debug("Sending %s => count=%s" % (k, v))

            log.info('counter', extra={
                "label": f"{self.couters_prefix}.{v}",
                "value": v,
                "timestamp": ts,
                "dimension": "counter",
                **self.metadata
            })

            # Clear the counter once the data is sent
            del(self.counters[k])
            stats += 1

    def __flush_gauges(self, stats, ts):
        for k, (v, t) in self.gauges.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    debug_log.debug("Expiring gauge %s (age: %s)" % (
                        k, ts - t))
                del(self.gauges[k])

                continue
            v = float(v)

            if self.debug:
                debug_log.debug("Sending %s => value=%s" % (k, v))

            log.info('gauge', extra={
                "label": f"{self.couters_prefix}.{v}",
                "value": v,
                "timestamp": ts,
                "dimension": "gauge",
                **self.metadata
            })

            stats += 1

    def __flush_timers(self, stats, ts):
        for k, (v, t) in self.timers.items():
            if self.expire > 0 and t + self.expire < ts:
                if self.debug:
                    debug_log.debug(f"Expiring timer {k} (age: {ts - t})")
                del(self.timers[k])

                continue

            if len(v) > 0:
                # Sort all the received values. We need it
                # to extract percentiles
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
                    debug_log.debug(
                        "Sending %s ====> lower=%s, mean=%s, upper=%s, "
                        "%dpct=%s, count=%s" % (k, min, mean, max,
                                                self.pct_threshold,
                                                max_threshold, count))

                log.info('timer', extra={
                    "label": f"{self.couters_prefix}.{v}",
                    "value": v,
                    "timestamp": ts,
                    "dimension": "timer",
                    "mean": mean,
                    "max": max,
                    "min": min,
                    "count": count,
                    "max_threshold": max_threshold,
                    "pct_threshold": self.pct_threshold,
                    **self.metadata
                })

                stats += 1

    def flush(self):
        ts = int(time.time())
        stats = 0
        self.__flush_counters(stats, ts)
        self.__flush_gauges(stats, ts)
        self.__flush_timers(stats, ts)

        if self.debug:
            debug_log.debug("\n================== Flush completed. "
                            "Waiting until next flush. "
                            "Sent out %d metrics =======" % (stats))

    def _set_timer(self):
        self._timer = threading.Timer(self.flush_interval / 1000,
                                      self.on_timer)
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
                debug_log.error("Bad data from %s: %s", addr, error)

    def stop(self):
        self._timer.cancel()
        self._sock.close()


class ServerDaemon(Daemon):
    def run(self, options):
        if setproctitle:
            setproctitle('statsd_to_logstash')
        server = Server(debug=options.debug,
                        logstash_host=options.logstash_host,
                        logstash_port=options.logstash_port,
                        flush_interval=options.flush_interval,
                        no_aggregate_counters=options.no_aggregate_counters,
                        expire=options.expire, metadata=options.metadata)

        server.serve(options.name, options.port)


def run_server():
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='debug mode', default=False)
    parser.add_argument('-n', '--name', dest='name',
                        help='hostname to run on ', default='')
    parser.add_argument('-p', '--port', dest='port',
                        help='port to run on (default: 8125)',
                        type=int, default=8125)

    parser.add_argument('-lp', '--logstash-port', dest='logstash_port',
                        help='Logstash Port (default: 5959)', type=int,
                        default=5959)
    parser.add_argument('-lh', '--logstash-host', dest='logstash_host',
                        help='Logstash Host (default: localhost)', type=str,
                        default='localhost')

    parser.add_argument('-m', '--metadata', dest='metadata',
                        help='Logstash extra metadata key1=value1,key2=value2',
                        type=str)

    parser.add_argument(
        '--flush-interval', dest='flush_interval',
        help='how often to send data in millis (default: 10000)', type=int,
        default=10000)
    parser.add_argument(
        '--no-aggregate-counters',  dest='no_aggregate_counters',
        help='should statsd report counters as absolute instead of count/sec',
        action='store_true')
    parser.add_argument('-D', '--daemon', dest='daemonize',
                        action='store_true', help='daemonize', default=False)
    parser.add_argument('--pidfile', dest='pidfile', action='store',
                        help='pid file', default='/var/run/statsd_to_logstash.pid')
    parser.add_argument('--restart', dest='restart', action='store_true',
                        help='restart a running daemon', default=False)
    parser.add_argument('--stop', dest='stop', action='store_true',
                        help='stop a running daemon', default=False)
    parser.add_argument('--expire', dest='expire',
                        help='time-to-live for old stats (in secs)', type=int,
                        default=0)
    options = parser.parse_args(sys.argv[1:])

    log_level = logging.DEBUG if options.debug else logging.INFO

    options.metadata = {
        kv.split('=')[0]: kv.split('=')[1]

        for kv in options.metadata.split(',')
    }

    log.addHandler(logstash.TCPLogstashHandler(options.logstash_host,
                                               options.logstash_port))
    debug_log.setLevel(log_level)
    debug_log.info("Starting up on %s" % options.port)
    daemon = ServerDaemon(options.pidfile)

    if options.daemonize:
        daemon.start(options)
    elif options.restart:
        daemon.restart(options)
    elif options.stop:
        daemon.stop()
    else:
        daemon.run(options)


log = logging.getLogger("statsd.server.report")
debug_log = logging.getLogger("statd.server.debug")

if __name__ == '__main__':
    run_server()
