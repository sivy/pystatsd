import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "pystatsd",
    version = "0.1.4",
    author = "Steve Ivy",
    author_email = "steveivy@gmail.com",
    description = ("pystatsd is a client for Etsy's brilliant statsd server, a front end/proxy for the Graphite stats collection and graphing server."),
    url='https://github.com/sivy/py-statsd',
    license = "BSD",
    packages=['pystatsd'],
    install_requires=['argparse >= 1.2'],
    long_description=read('README'),
    requires=['argparse'],
    classifiers=[
        "License :: OSI Approved :: BSD License",
    ],
    scripts=['bin/pystatd-server']
)
