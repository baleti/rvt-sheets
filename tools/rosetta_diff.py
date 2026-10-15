"""rosetta_diff.py BASE VAR -> differences of the decoded view/sheet model (views, sheets, filters)"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
a = json.loads(json.dumps(Decoder(sys.argv[1]).doc(), default=lambda o: int(o) if hasattr(o, '__int__') else repr(o)))
b = json.loads(json.dumps(Decoder(sys.argv[2]).doc(), default=lambda o: int(o) if hasattr(o, '__int__') else repr(o)))
def diff(x, y, p=''):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=str):
            if k in ('params',) : continue
            diff(x.get(k), y.get(k), p + '.' + str(k))
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (u, v) in enumerate(zip(x, y)): diff(u, v, p + '[%d]' % i)
    elif x != y:
        if isinstance(x, float) and isinstance(y, float) and abs(x - y) < 1e-9: return
        print(p, ':', json.dumps(x)[:200], '->', json.dumps(y)[:200])
for k in ('views', 'sheets', 'filters'): diff(a[k], b[k], k)
