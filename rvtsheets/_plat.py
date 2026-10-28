"""lazy access to rvtplat (installed, sibling checkout or ~/src/rvtplat)"""
import os, sys, importlib


def _mod(name):
    try: return importlib.import_module('rvtplat.' + name)
    except ImportError:
        for d in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'rvtplat'), os.path.join(os.path.expanduser('~'), 'src', 'rvtplat')):
            if os.path.isdir(os.path.join(d, 'rvtplat')) and d not in sys.path: sys.path.insert(0, d)
        return importlib.import_module('rvtplat.' + name)


def render(): return _mod('render')
def fonts(): return _mod('fonts')
def fsio(): return _mod('fsio')
