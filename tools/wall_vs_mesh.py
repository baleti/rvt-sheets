"""wall_vs_mesh.py FILE VIEWID EID... : walker solid vs reader element mesh per wall: triangle count, bbox, signed volume, area of faces"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvtsheets.viewdraw as VD
import rvt_elemmesh as E
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2]); W = {int(x) for x in sys.argv[3:]}
def stat(t):
    t = np.asarray(t, float).reshape(-1, 3, 3)
    vol = float(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6)
    area = float(np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum() / 2)
    return len(t), np.round(t.reshape(-1, 3).min(0), 1).tolist(), np.round(t.reshape(-1, 3).max(0), 1).tolist(), round(vol, 1), round(area, 1)
orig = VD.Walker.walk_record
def wr(self, eid, *a, **k):
    r = orig(self, eid, *a, **k)
    if eid in W:
        for s in r['solids']:
            T = vd._tess(s)
            if T is not None: print(eid, 'walker', stat(T[0]))
        m = E.element_mesh(vd.f.g, eid).get('tris')
        print(eid, 'mesh  ', stat(m) if m is not None and len(m) else None)
    return r
VD.Walker.walk_record = wr
vd.draw(vid)
