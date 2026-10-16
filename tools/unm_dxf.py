"""unm_dxf.py FILE VIEWID DXF [LAYERS] : our line prims (layers symbolic/projection/cut...) that have no Revit DXF line within 0.01 ft, grouped by element (class, category, unmatched / total length ft).
Offset 0 (views whose compare_dxf registration offset is 0). Prints the worst 15 elements."""
import sys, os, collections
sys.path.insert(0, __file__.rsplit('/', 2)[0])
import numpy as np, ezdxf
from shapely.geometry import LineString
from shapely import STRtree
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn, vid, dxf = sys.argv[1], int(sys.argv[2]), sys.argv[3]
layers = set(sys.argv[4].split(',')) if len(sys.argv) > 4 else {'symbolic', 'projection', 'cut', 'underlay'}
dec = Decoder(fn); doc = dec.doc(); d = ViewDrawer(dec, doc); dr = d.draw(vid)
v = doc['views'][vid]; O, X, Y, Z = d.frame(v)
if v['kind'] == 'plan': to_view = lambda x, y: ((x - O[0]) * X[0] + (y - O[1]) * X[1], (x - O[0]) * Y[0] + (y - O[1]) * Y[1])
else: to_view = lambda x, y: (x - float(O @ X), y - float(O @ Y))
dx = ezdxf.readfile(dxf); rev = []
K = {1: 1 / 12, 2: 1.0, 4: 1 / 304.8, 5: 1 / 30.48, 6: 1 / 0.3048}.get(dx.header.get('$INSUNITS', 0), 1.0)
def walk(es):
    for e in es:
        if e.dxftype() == 'INSERT':
            try: walk(e.virtual_entities())
            except Exception: pass
        elif e.dxftype() == 'LINE': rev.append(LineString([to_view(e.dxf.start.x * K, e.dxf.start.y * K), to_view(e.dxf.end.x * K, e.dxf.end.y * K)]))
        elif e.dxftype() in ('LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'SPLINE', 'ELLIPSE'):
            try:
                pts = [to_view(p.x * K, p.y * K) for p in e.flattening(0.01)]
                if len(pts) > 1: rev.append(LineString(pts))
            except Exception: pass
walk(dx.modelspace())
tree = STRtree(rev); bad = collections.Counter(); tot = collections.Counter()
def segs_of(p):
    if p['t'] == 'line':
        pts = np.asarray(p['pts'], float)[:, :2]; return [pts] if len(pts) > 1 else []
    return [np.asarray(sg, float)[:, :2] for sg in p.get('segs') or []]
for p in dr['prims']:
    if p['t'] not in ('line', 'segs', 'cut') or p.get('layer') not in layers: continue
    for pl in segs_of(p):
      for pts in [pl[i:i + 2] for i in range(len(pl) - 1)]:        # per segment: Revit's polylines are split into pieces
        if len(pts) < 2: continue
        ls = LineString(pts); L = ls.length
        if L < 0.05: continue
        ok = any(rev[i].buffer(0.01).intersection(ls).length > 0.6 * L for i in tree.query(ls.buffer(0.01)))
        k = p.get('elem'); tot[k] += L
        if not ok: bad[k] += L
info = d.vis.info.info
Mv = np.stack([X, Y, Z])
def depth(e):
    bb = d.vis.info.bbox(e)
    if bb is None: return None
    c = np.array([[bb[i][0], bb[j][1], bb[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)]); loc = (c - O) @ Mv.T
    return round(float(loc[:, 2].max()), 1), round(float(loc[:, 2].min()), 1)
for k, v in bad.most_common(int(os.environ.get('TOPN', '15'))):
    i = info.get(k) or {}; print(k, i.get('cls'), (doc['categories'].get(i.get('cat')) or {}).get('name'), round(v, 1), '/', round(tot[k], 1), 'depth', depth(k))
if os.environ.get('DEPTHSUM'):
    agg = collections.defaultdict(lambda: [0.0, 0.0])
    for k in tot:
        dp = depth(k)
        if dp is None: continue
        key = 'front(all>0)' if dp[1] > 0 else 'behind(all<0)' if dp[0] < 0 else 'straddles'
        agg[key][0] += bad.get(k, 0); agg[key][1] += tot[k]
    print({k: (round(a, 1), round(b, 1)) for k, (a, b) in agg.items()})
