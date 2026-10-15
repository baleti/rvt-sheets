"""dxf_overlay.py FILE VIEWID REVIT.dxf OUT.png [layer_substring] -> red = Revit DXF, blue = ours (view coordinates), optional layer filter for Revit"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compare_dxf as C
ours, v, O, X, Y = C.our_segments(sys.argv[1], int(sys.argv[2]))
rv, k = C.dxf_segments(sys.argv[3]); flt = sys.argv[5] if len(sys.argv) > 5 else ''
def tov(P):
    if v['kind'] != 'plan': return P
    return np.stack([(P[:, 0] - O[0]) * X[0] + (P[:, 1] - O[1]) * X[1], (P[:, 0] - O[0]) * Y[0] + (P[:, 1] - O[1]) * Y[1]], 1)
rv = [(l, tov(P)) for l, P in rv if flt in l]
allp = np.concatenate([P for _, P in rv] + [P for _, P in ours])
lo, hi = np.percentile(allp, 1, 0), np.percentile(allp, 99, 0)
W = 2000; s = W / max(hi - lo); H = int((hi[1] - lo[1]) * s) + 20
im = Image.new('RGB', (W + 20, H), 'white'); d = ImageDraw.Draw(im)
T = lambda P: [(10 + (x - lo[0]) * s, H - 10 - (y - lo[1]) * s) for x, y in P]
for _, P in rv: d.line(T(P), fill=(230, 60, 60), width=3)
for _, P in ours: d.line(T(P), fill=(40, 80, 220), width=1)
im.save(sys.argv[4])
