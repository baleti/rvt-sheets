"""probe_tess.py FILE VIEWID EID : the shaded 3D path of an element: Walker solids -> drawer._tess triangles (count, area, bbox) next to rvt_elemmesh.element_mesh"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.scene import Walker, ViewCtx
import rvt_elemmesh as E
import numpy as np
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2])
v = doc['views'][vid]; Z = np.asarray(v['dir'], float)
W = Walker(vd.f, ViewCtx(Z, detail=3, kind='3d', scale=1)); W.is_2d = lambda e: False; W.invisible_gs = set()
def stat(T):
    T = np.asarray(T, float).reshape(-1, 3, 3); n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    return 'tris %d area %.2f bbox %s %s' % (len(T), np.linalg.norm(n, axis=1).sum() / 2, T.reshape(-1, 3).min(0).round(1), T.reshape(-1, 3).max(0).round(1))
for eid in map(int, sys.argv[3:]):
    p = W.walk_record(eid); print(eid, 'solids', len(p['solids']))
    for s in p['solids']:
        t = vd._tess(s); print('   _tess', None if t is None else stat(t[0]))
    print('   element_mesh', stat(E.element_mesh(vd.f.g, eid).get('tris') or []))
