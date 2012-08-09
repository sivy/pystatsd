"""A generic daemon class. Subclass and override the run() method.

Based on http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
"""

from __future__ import with_statement

import atexit
import os
from signal import SIGTERM
import sys
import time


class Daemon(object):
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null',
                 stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """UNIX double-fork magic."""
        try:
            pid = os.fork()
            if pid > 0:
                # First parent; exit.
                sys.exit(0)
        except OSError, e:
            sys.stderr.write('Could not fork! %d (%s)\n' %
                             (e.errno, e.strerror))
            sys.exit(1)

        # Disconnect from parent environment.
        os.chdir('/')
        os.setsid()
        os.umask(0022)

        # Fork again.
        try:
            pid = os.fork()
            if pid > 0:
                # Second parent; exit.
                sys.exit(0)
        except OSError, e:
            sys.stderr.write('Could not fork (2nd)! %d (%s)\n' %
                             (e.errno, e.strerror))
            sys.exit(1)

        # Redirect file descriptors.
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # Write the pidfile.
        atexit.register(self.delpid)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+') as fp:
            fp.write('%s\n' % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def start(self, *args, **kw):
        """Start the daemon."""
        pid = None
        if os.path.exists(self.pidfile):
            with open(self.pidfile, 'r') as fp:
                pid = int(fp.read().strip())

        if pid:
            msg = 'pidfile (%s) exists. Daemon already running?\n'
            sys.stderr.write(msg % self.pidfile)
            sys.exit(1)

        self.daemonize()
        self.run(*args, **kw)

    def stop(self):
        """Stop the daemon."""
        pid = None
        if os.path.exists(self.pidfile):
            with open(self.pidfile, 'r') as fp:
                pid = int(fp.read().strip())

        if not pid:
            msg = 'pidfile (%s) does not exist. Daemon not running?\n'
            sys.stderr.write(msg % self.pidfile)
            return

        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, e:
            e = str(e)
            if e.find('No such process') > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
                else:
                    print e
                    sys.exit(1)

    def restart(self, *args, **kw):
        """Restart the daemon."""
        self.stop()
        self.start(*args, **kw)

    def run(self, *args, **kw):
        """Override this method."""
