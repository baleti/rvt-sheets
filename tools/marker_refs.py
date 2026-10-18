"""marker_refs.py FILE ID... : which view records reference the given element ids (field paths), to find how markers are tied to plans"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
dec = Decoder(sys.argv[1]); f = dec.f; want = {int(x) for x in sys.argv[2:]}
def walk(x, p, out):
    if isinstance(x, dict):
        for k, v in x.items(): walk(v, p + '.' + str(k), out)
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x[:400]): walk(v, p + '[]', out)
    else:
        try:
            if int(x) in want and not isinstance(x, (float, bool)): out.add(p)
        except Exception: pass
import collections
hits = collections.defaultdict(set)
for eid, rs in f.byid.items():
    for r in rs:
        if r['id'] in want: continue
        out = set(); walk(r['fields'], '', out)
        if out: hits[r['class']] |= {p for p in out}; hits[r['class'] + '#ids'] |= {eid}
for k, v in hits.items():
    print(k, sorted(v)[:12] if not k.endswith('#ids') else len(v))
