"""plan_fielddiff.py FILE GOODIDS(comma) BADID : scalar fields of DBViewPlan / Viewer records where BADID differs from all GOOD ones that agree among themselves"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
dec = Decoder(sys.argv[1]); f = dec.f
good = [int(x) for x in sys.argv[2].split(',')]; bad = int(sys.argv[3])
def flat(x, p, out, depth=0):
    if depth > 6: return
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ('m_id', 'm_pGeomTable', 'm_docAccess'): continue
            flat(v, p + '.' + str(k), out, depth + 1)
    elif isinstance(x, (list, tuple)):
        out[p + '#len'] = len(x)
        for i, v in enumerate(x[:6]): flat(v, p + '[%d]' % i, out, depth + 1)
    else: out[p] = x if isinstance(x, (int, float, str, bool, type(None))) else str(x)[:60]
def get(vid):
    r = f.rec(vid); o = {}; flat(r['fields'], '', o); return o
G = [get(v) for v in good]; B = get(bad)
for k in sorted(set(B) | set().union(*G)):
    gv = [g.get(k, '<none>') for g in G]
    if len({str(x) for x in gv}) == 1 and str(B.get(k, '<none>')) != str(gv[0]): print(k, 'good', gv[0], 'bad', B.get(k, '<none>'))
