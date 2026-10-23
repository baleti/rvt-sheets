"""elem_prim_dump.py FILE VIEWID EID...: every prim of the elements (type, layer, part, point count, first / last point, text)"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); dr = vd.draw(int(sys.argv[2]))
for e in [int(a) for a in sys.argv[3:]]:
    for p in dr['prims']:
        if p.get('elem') != e: continue
        pts = p.get('pts') or ([q for s in p.get('segs', []) for q in s]) or [q for l in p.get('loops', []) for q in l]
        a = np.round(np.asarray(pts, float)[:, :2], 1).tolist() if len(pts) else []
        print(e, p['t'], p.get('layer'), p.get('part'), len(pts), a[:1], a[-1:], p.get('text', ''))
