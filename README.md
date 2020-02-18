Introduction
------------

**pystatsd** is a client and server implementation of Etsy's brilliant statsd
server, a front end/proxy for the Graphite stats collection and graphing server.

* Graphite
    - http://graphite.wikidot.com
* Statsd
    - code: https://github.com/etsy/statsd
    - blog post: http://codeascraft.etsy.com/2011/02/15/measure-anything-measure-everything/

**pystatsd** is [tested on](https://github.com/sivy/pystatsd/actions) Python 2.7 and 3.8.

Status
-------------

Reviewing and merging pull requests, bringing stuff up to date, with tests!

[![lint_python](https://github.com/sivy/pystatsd/workflows/lint_python/badge.svg)](https://github.com/sivy/pystatsd/actions)

Usage
-------------

See statsd_test for sample usage:

    from pystatsd import Client, Server

    srvr = Server(debug=True)
    srvr.serve()

    sc = Client('example.org',8125)

    sc.timing('python_test.time',500)
    sc.increment('python_test.inc_int')   # or sc.incr()
    sc.decrement('python_test.decr_int')  # or sc.decr()
    sc.gauge('python_test.gauge', 42)

Building a Debian Package
-------------

To build a debian package, run `dpkg-buildpackage -rfakeroot`

Upstart init Script
-------------
Upstart is the daemon management system for Ubuntu.

A basic upstart script has been included for the pystatsd server. It's located
under init/, and will be installed to /usr/share/doc if you build/install a
.deb file. The upstart script should be copied to /etc/init/pystatsd.conf and
will read configuration variables from /etc/default/pystatsd. By default the
pystatsd daemon runs as user 'nobody' which is a good thing from a security
perspective.

Troubleshooting
-------------

You can see the raw values received by pystatsd by packet sniffing:

    $ sudo ngrep -qd any . udp dst port 8125

You can see the raw values dispatched to carbon by packet sniffing:

    $ sudo ngrep -qd any stats tcp dst port 2003
