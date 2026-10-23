"""extra_elems.py FILE VIEWID REVIT.dxf -> our drawn elements ranked by length of ink with no Revit ink nearby (paper mm), with class / category / bbox z.
Uses compare_dxf's masking-free per-primitive samples (prims of the draw, no mask / crop processing), registration offset 0 (plans)."""
import sys, os, collections
import numpy as np
sys.path.insert(0, '/home/user1/src/rvt-sheets-dev'); sys.path.insert(0, '/home/user1/src/rvt-sheets-dev/tools')
import compare_dxf as C
from scipy.spatial import cKDTree
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn, vid, dxf = sys.argv[1], int(sys.argv[2]), sys.argv[3]
dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc); dr = vd.draw(vid); v = doc['views'][vid]
O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
scale = v.get('scale') or 100; step = 0.25 / 304.8 * scale; tol = 0.5 / 304.8 * scale
rv, k = C.dxf_segments(dxf)
B3, lb = C.sample(rv, step)
B = np.stack([(B3[:, 0] - O[0]) * X[0] + (B3[:, 1] - O[1]) * X[1], (B3[:, 0] - O[0]) * Y[0] + (B3[:, 1] - O[1]) * Y[1]], 1) if v['kind'] == 'plan' else B3 - np.array([float(O @ X), float(O @ Y)])
tb = cKDTree(B)
tot = collections.Counter(); bad = collections.Counter(); info = {}
for p in dr['prims']:
    if p.get('layer') in C.HATCH_LAYERS or p.get('layer') in ('mask',) or p['t'] not in ('line', 'segs', 'cut'): continue
    segs = [p['pts']] if p['t'] == 'line' else p['segs']
    P = [np.asarray(s, float)[:, :2] for s in segs if len(s) > 1]
    if not P: continue
    A, _ = C.sample([('x', q) for q in P], step)
    if not len(A): continue
    d = tb.query(A)[0]
    key = (p.get('elem'), p.get('layer'))
    tot[key] += len(A); bad[key] += int((d > tol).sum())
for key, n in sorted(bad.items(), key=lambda kv: -tot[kv[0]])[:int(os.environ.get('TOPN','25'))]:
    e = key[0]; r = dec.f.rec(e) if e else None; bb = vd.vis.info.bbox(e) if e else None
    print(key, 'extra mm %.0f of %.0f' % (n * 0.25, tot[key] * 0.25), r['class'] if r else None, vd.vis.info.info.get(e, {}).get('cat'), None if bb is None else (round(float(bb[0][2]), 1), round(float(bb[1][2]), 1)))
