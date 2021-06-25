Introduction
------------

**statsd_to_logstash** is a client and server implementation of Etsy's brilliant statsd
server, a front end/proxy for the Graphite stats collection and graphing server.

* Graphite
    - http://graphite.wikidot.com
* Statsd
    - code: https://github.com/etsy/statsd
    - blog post: http://codeascraft.etsy.com/2011/02/15/measure-anything-measure-everything/

**statsd_to_logstash** is [tested on](https://github.com/YonatanKiron/statsd_to_logstash/actions) Python 2.7 and 3.8.

Status
-------------

Reviewing and merging pull requests, bringing stuff up to date, with tests!

[![lint_python](https://github.com/YonatanKiron/statsd_to_logstash/workflows/lint_python/badge.svg)](https://github.com/YonatanKiron/statsd_to_logstash/actions)

Usage
-------------

See statsd_test for sample usage:

    from statsd_to_logstash import Server

    srvr = Server(debug=True)
    srvr.serve()

    sc = Client('example.org',8125)

Building a Debian Package
-------------

To build a debian package, run `dpkg-buildpackage -rfakeroot`

Upstart init Script
-------------
Upstart is the daemon management system for Ubuntu.

A basic upstart script has been included for the statsd_to_logstash server. It's located
under init/, and will be installed to /usr/share/doc if you build/install a
.deb file. The upstart script should be copied to /etc/init/statsd_to_logstash.conf and
will read configuration variables from /etc/default/statsd_to_logstash. By default the
statsd_to_logstash daemon runs as user 'nobody' which is a good thing from a security
perspective.

Troubleshooting
-------------

You can see the raw values received by statsd_to_logstash by packet sniffing:

    $ sudo ngrep -qd any . udp dst port 8125

You can see the raw values dispatched to carbon by packet sniffing:

    $ sudo ngrep -qd any stats tcp dst port 2003
