"""p20_probe.py FILE VID VID... : DBView record scalar fields that differ between the views (flat walk, depth 4)"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); d.doc(); vs = [int(x) for x in sys.argv[2:]]
def flat(o, path='', depth=0, out=None):
    out = {} if out is None else out
    if depth > 6: return out
    if isinstance(o, dict):
        for k, v in o.items(): flat(v, path + '.' + str(k), depth + 1, out)
    elif isinstance(o, list):
        if len(o) < 40:
            for i, v in enumerate(o): flat(v, path + '[%d]' % i, depth + 1, out)
        else: out[path] = 'len%d' % len(o)
    else: out[path] = str(o)[:80]
    return out
F = {v: flat(d.f.rec(v)['fields']) for v in vs}
keys = sorted({k for f in F.values() for k in f})
for k in keys:
    vals = [F[v].get(k) for v in vs]
    if len(set(vals)) > 1 and not any(s in k for s in ('m_id', 'Id', 'm_viewName', 'm_name', 'm_uniqueId', 'ptr', 'handle', 'm_origin', 'm_pos', 'Guid', 'GUID', 'm_cachedModel')): print('P', k, ' | '.join(map(str, vals)))
