"""ray_probe.py FILE VIEWID Y Z XMIN : listed elements whose reader mesh a ray along world -x at (y, z) crosses at x > XMIN (what hides a point of an east elevation)"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.viewdraw import ViewDrawer
import rvt_elemmesh as E
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); vid = int(sys.argv[2]); y, z, x0 = map(float, sys.argv[3:6])
g = ViewDrawer(dec, doc).f.g
for i in vis.elements(vid):
    bb = vis.info.bbox(i)
    if bb is None or not (bb[0][1] - .01 <= y <= bb[1][1] + .01 and bb[0][2] - .01 <= z <= bb[1][2] + .01 and bb[1][0] > x0): continue
    try: T = np.asarray(E.element_mesh(g, i).get('tris') or [], float).reshape(-1, 3, 3)
    except Exception: T = np.zeros((0, 3, 3))
    hits = []
    for t in T:
        a, b, c = t[:, 1:]; d = (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])
        if abs(d) < 1e-12: continue
        p = np.array([y, z]) - a; u = (p[0] * (c[1] - a[1]) - p[1] * (c[0] - a[0])) / ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) if False else None
        # barycentric in (y, z)
        M = np.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
        if abs(np.linalg.det(M)) < 1e-12: continue
        s, tt = np.linalg.solve(M, p)
        if s >= -1e-9 and tt >= -1e-9 and s + tt <= 1 + 1e-9: hits.append(t[0][0] + s * (t[1][0] - t[0][0]) + tt * (t[2][0] - t[0][0]))
    if hits:
        e = vis.info.info.get(i, {}); print(i, e.get('cls'), e.get('cat'), 'x hits', np.round(sorted(hits), 1).tolist()[:6], 'ntris', len(T))
