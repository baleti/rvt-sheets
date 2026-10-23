"""sym_probe.py FILE VIEWID : per element, layer 'symbolic' prim counts, straight 2-point lines and their total length (feet, view coordinates), with class/category"""
import sys, os, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); vid = int(sys.argv[2])
dr = ViewDrawer(dec, doc).draw(vid)
agg = collections.defaultdict(lambda: [0, 0.0, 0])
for p in dr['prims']:
    if p.get('layer') != 'symbolic': continue
    for pts in ([p['pts']] if p.get('t') == 'line' else p.get('segs') or []):
        a = np.asarray(pts, float)
        if a.ndim != 2 or len(a) < 2: continue
        L = float(np.linalg.norm(np.diff(a[:, :2], axis=0), axis=1).sum())
        e = agg[p.get('elem')]; e[0] += 1; e[1] += L; e[2] += (len(a) == 2)
for eid, (n, L, n2) in sorted(agg.items(), key=lambda t: -t[1][1])[:25]:
    e = vis.info.info.get(eid, {}); print(eid, e.get('cls'), e.get('cat'), 'prims', n, 'two-point', n2, 'len ft %.1f' % L)
