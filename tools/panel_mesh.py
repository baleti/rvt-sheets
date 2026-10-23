"""panel_mesh.py FILE VIEWID EID... : walker solid (tris, bbox) vs the reader's element mesh (tris, bbox) per element"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvtsheets.viewdraw as VD
import rvt_elemmesh as E
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2]); W = {int(x) for x in sys.argv[3:]}
orig = VD.Walker.walk_record
def wr(self, eid, *a, **k):
    r = orig(self, eid, *a, **k)
    if eid in W:
        for s in r['solids']:
            T = vd._tess(s)
            if T is None: print(eid, 'walker tess None'); continue
            t = np.asarray(T[0], float).reshape(-1, 3)
            print(eid, 'walker tris', len(t) // 3, 'bbox', np.round(t.min(0), 2).tolist(), np.round(t.max(0), 2).tolist())
        try:
            m = np.asarray(E.element_mesh(vd.f.g, eid).get('tris') or [], float).reshape(-1, 3)
            print(eid, 'mesh tris', len(m) // 3, 'bbox', np.round(m.min(0), 2).tolist() if len(m) else None, np.round(m.max(0), 2).tolist() if len(m) else None)
        except Exception as ex: print(eid, 'mesh error', ex)
    return r
VD.Walker.walk_record = wr
vd.draw(vid)
