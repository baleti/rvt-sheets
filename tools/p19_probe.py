"""p19_probe.py FILE EID... : plan area of the element's reader mesh (union of triangle footprints, sq ft) and its bbox"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
import rvt_elemmesh as E
from shapely.geometry import Polygon
from shapely.ops import unary_union
d = Decoder(sys.argv[1]); d.doc()
for e in map(int, sys.argv[2:]):
    T = np.asarray(E.element_mesh(d.f.g, e).get('tris') or [], float).reshape(-1, 3, 3)
    pg = [Polygon(t[:, :2]) for t in T if abs(t[0, 2] - t[1, 2]) < 1e-6 and abs(t[1, 2] - t[2, 2]) < 1e-6]
    u = unary_union([p for p in pg if p.is_valid and p.area > 1e-9])
    print('P', e, 'tris', len(T), 'flat tris', len(pg), 'union area', round(u.area, 1), 'bbox', T.reshape(-1, 3).min(0).round(1).tolist(), T.reshape(-1, 3).max(0).round(1).tolist())
