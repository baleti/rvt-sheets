"""p6_probe.py FILE EID SUBSTR : record fields (any depth) whose key contains SUBSTR, with a short value"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); d.doc(); sub = sys.argv[3].lower()
def walk(o, path, depth=0):
    if depth > 6: return
    if isinstance(o, dict):
        for k, v in o.items():
            if sub in str(k).lower(): print('P', path + '.' + str(k), str(v)[:240])
            walk(v, path + '.' + str(k), depth + 1)
    elif isinstance(o, list):
        for i, v in enumerate(o[:50]): walk(v, path + '[%d]' % i, depth + 1)
walk(d.f.rec(int(sys.argv[2]))['fields'], '')
