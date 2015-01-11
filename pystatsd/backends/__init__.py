from .ganglia import Ganglia
from .gmetric import Gmetric
from .graphite import Graphite
from .console import Console

def create_instance(transport, options):
    if transport == 'graphite':
        return Graphite(options)
    elif transport == 'ganglia':
        return Ganglia(options)
    elif transport == 'ganglia-gmetric':
        return Gmetric(options)
    elif transport == 'console':
        return Console(options)
    else:
        return None
