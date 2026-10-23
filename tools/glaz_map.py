"""glaz_map.py FILE VIEWID REVIT.dxf LAYERSUB : x extent (view feet) of Revit's layer segments in clusters vs the x extent of our prims per curtain-category element."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compare_dxf as C
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
rv, k = C.dxf_segments(sys.argv[3])
xs = np.concatenate([P[:, 0] for l, P in rv if sys.argv[4] in l])
print('revit', sys.argv[4], 'x range', xs.min(), xs.max(), 'n', len(xs))
h = np.histogram(xs, bins=40); print([int(c) for c in h[0]]); print([round(float(b), 1) for b in h[1]])
dec = Decoder(sys.argv[1]); doc = dec.doc(); dr = ViewDrawer(dec, doc).draw(int(sys.argv[2]))
import collections
ext = collections.defaultdict(lambda: [1e9, -1e9])
for p in dr['prims']:
    pts = p.get('pts')
    if pts is None or p.get('cat') not in (-2000170, -2000171, -2000011): continue
    a = np.asarray(pts, float)
    if a.ndim != 2: continue
    e = ext[(p.get('elem'), p.get('cat'))]; e[0] = min(e[0], a[:, 0].min()); e[1] = max(e[1], a[:, 0].max())
for k2, v in sorted(ext.items(), key=lambda t: t[1][0])[:60]: print(k2, [round(x, 1) for x in v])
print('prim keys', list(dr['prims'][0].keys()))
