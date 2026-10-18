"""probe_color.py FILE VIEWID R G B : elements of the view whose mesh material colour is near (R,G,B): id, class, category, bbox, triangle count"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvt_elemmesh as E
import numpy as np
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); f = vd.f
tgt = np.array([float(x) for x in sys.argv[3:6]]); info = vd.vis.info.info
mats = vd.materials()
for eid in vd.vis.elements(int(sys.argv[2])):
    try: m = E.element_mesh(f.g, eid)
    except Exception: continue
    T = np.asarray(m.get('tris') or [], float).reshape(-1, 3, 3)
    if not len(T): continue
    mat = m.get('mat'); cols = []
    for k in (mat if isinstance(mat, (list, tuple, np.ndarray)) else [mat]):
        try: mm = mats.get(int(k)) or {}
        except Exception: mm = {}
        c = mm.get('color') or mm.get('rgb')
        if c: cols.append((mm.get('name'), tuple(c[:3])))
    if any(np.abs(np.array(c)-tgt).max() < 20 for _, c in cols):
        print(eid, info[eid]['cls'], info[eid]['cat'], 'tris', len(T), 'bbox', T.reshape(-1,3).min(0).round(1), T.reshape(-1,3).max(0).round(1), set(n for n,_ in cols))
