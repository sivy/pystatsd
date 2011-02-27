Introduction
------------

pystatsd is a client for Etsy's brilliant statsd server, a front end/proxy for the Graphite stats collection and graphing server.

* Graphite
    - http://graphite.wikidot.com
* Statsd 
    - code: https://github.com/etsy/statsd
    - blog post: http://codeascraft.etsy.com/2011/02/15/measure-anything-measure-everything/

Usage
-------------

See statsd_test for sample usage:

    from pystatsd import Client, Server

    sc = Client('rayners.org',8125)

    sc.timing('python_test.time',500)
    sc.increment('python_test.inc_int')
    sc.decrement('python_test.decr_int')

    srvr = Server(debug=True)
    srvr.serve()
