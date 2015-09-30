Introduction
------------

**pystatsd** is a client and server implementation of Etsy's brilliant statsd
server, a front end/proxy for the Graphite stats collection and graphing server.

* Graphite
    - http://graphite.wikidot.com
* Statsd
    - code: https://github.com/etsy/statsd
    - blog post: http://codeascraft.etsy.com/2011/02/15/measure-anything-measure-everything/

**pystatsd** has [been tested on](http://travis-ci.org/sivy/py-statsd) python 2.7 and 3.4.

Status
-------------

Reviewing and merging pull requests, bringing stuff up to date, now with tests!

[![Build Status](https://secure.travis-ci.org/sivy/py-statsd.png?branch=master)](http://travis-ci.org/sivy/py-statsd)



Usage
-------------

See statsd_test for sample usage:

    from pystatsd import Client, Server

    srvr = Server(debug=True)
    srvr.serve()

    sc = Client('example.org',8125)

    sc.timing('python_test.time',500)
    sc.increment('python_test.inc_int')
    sc.decrement('python_test.decr_int')
    sc.gauge('python_test.gauge', 42)

or, to run the server from a simple command, if you have the package installed:

    $ pystatsd-server

Check out the options for the command for more information:

    $ pystatsd-server --help


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

Developing
-------------

Make sure you have `tox` installed, then just run the tests:

    $ make test

Troubleshooting
-------------

You can see the raw values received by pystatsd by packet sniffing:

    $ sudo ngrep -qd any . udp dst port 8125

You can see the raw values dispatched to carbon by packet sniffing:

    $ sudo ngrep -qd any stats tcp dst port 2003
