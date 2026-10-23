"""wall_curtain.py FILE VIEWID : walls the view lists with bbox, number of curtain panels/mullions whose bbox centre lies inside, and field names / values mentioning curtain or grid"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); vid = int(sys.argv[2])
ids = vis.elements(vid); inf = vis.info.info
cur = []
for i in ids:
    if inf.get(i, {}).get('cat') in (-2000170, -2000171):
        b = vis.info.bbox(i)
        if b is not None: cur.append((i, (np.asarray(b[0]) + np.asarray(b[1])) / 2))
for i in ids:
    e = inf.get(i, {})
    if e.get('cat') not in (-2000011, -2003500): continue
    b = vis.info.bbox(i)
    if b is None: continue
    lo, hi = np.asarray(b[0]), np.asarray(b[1])
    n = sum(1 for _, c in cur if (c >= lo - 0.05).all() and (c <= hi + 0.05).all())
    r = dec.f.rec(i) or {}; fl = r.get('fields') or {}
    ck = {k: (v if isinstance(v, (int, float, str)) else type(v).__name__) for k, v in fl.items() if 'urtain' in k or 'rid' in k or 'ype' in k.lower()}
    print(i, e.get('cls'), e.get('cat'), 'type', e.get('type'), 'n_inside', n, 'bbox', np.round(np.r_[lo, hi], 1).tolist(), ck)
