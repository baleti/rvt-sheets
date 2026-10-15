"""view_diag.py FILE VIEWID -> per element class: prims by layer + extents"""
import sys, os, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vd = ViewDrawer(dec, doc); dr = vd.draw(vid)
agg = collections.defaultdict(lambda: [collections.Counter(), [1e9, 1e9], [-1e9, -1e9]])
for p in dr['prims']:
    c = vd.vis.info.info[p['elem']]['cls'] + ':' + str((doc['categories'].get(vd.vis.info.info[p['elem']]['cat']) or {}).get('name'))
    a = agg[c]; a[0][p['layer']] += 1
    pts = p.get('pts') or [q for l in p.get('loops') or [] for q in l] + [q for s in p.get('segs') or [] for q in s]
    if pts:
        P = np.asarray(pts)[:, :2]; a[1] = np.minimum(a[1], P.min(0)).tolist(); a[2] = np.maximum(a[2], P.max(0)).tolist()
for c, (cnt, lo, hi) in sorted(agg.items(), key=lambda kv: -sum(kv[1][0].values())):
    print('%-45s %-60s %s %s' % (c[:45], dict(cnt), np.round(lo, 1), np.round(hi, 1)))
