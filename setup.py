import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "pystatsd",
    version = "0.0.1",
    author = "Steve Ivy",
    author_email = "steveivy@gmail.com",
    description = (""),
    license = "BSD",
    packages=['py-statsd'],
    long_description=read('README.txt'),
    classifiers=[
        "License :: OSI Approved :: BSD License",
    ],
)