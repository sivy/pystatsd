import os
from setuptools import setup
from statsd_to_logstash import VERSION

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "statsd-to-logstash",
    version=".".join(map(str, VERSION)),
    author = "Yonatan Kiron",
    author_email = "yonatankiron@gmail.com",
    description = ("statsd-to-logstash is a client for Etsy's statsd server, a front end/proxy for the logstash server."),
    url='https://github.com/YonatanKiron/statsd-to-logstash',
    license = "BSD",
    packages=['statsd-to-logstash'],
    long_description=read('README.md'),
    classifiers=[
        "Programming Language :: Python :: 3.8"
    ],
    install_requires=[
        "python3-logstash==0.4.80"
    ],
    scripts=['bin/statsd-to-logstash-server']
)
