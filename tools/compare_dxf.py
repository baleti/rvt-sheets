"""compare_dxf.py FILE.rvt VIEWID REVIT.dxf [--register] -> linework agreement of our view drawing vs Revit's DXF export of the same view.
Both sides are reduced to 2D segments (DXF: LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE/SPLINE flattened, INSERTs exploded; units feet or inches
detected from $INSUNITS); samples every 1/4 of a paper mm; a sample matches when the other side has ink within tol (paper mm).
Reports precision (our samples near Revit) / recall (Revit samples near ours) overall and per DXF layer, plus the registration offset."""
import sys, os, math, json, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scipy.spatial import cKDTree


def dxf_segments(fn):
    import ezdxf
    from ezdxf import path as zpath
    doc = ezdxf.readfile(fn)
    u = doc.header.get('$INSUNITS', 0)
    k = {1: 1 / 12, 2: 1.0, 4: 1 / 304.8, 5: 1 / 30.48, 6: 1 / 0.3048}.get(u, 1.0)
    out = []
    def emit(e, layer):
        try:
            p = zpath.make_path(e)
            pts = np.array([[v.x, v.y] for v in p.flattening(0.01 / k)])
            if len(pts) >= 2: out.append((layer, pts * k))
        except Exception: pass
    def walk(ents):
        for e in ents:
            t = e.dxftype()
            if t in ('INSERT', 'DIMENSION'):                 # dimensions: their anonymous block (lines, ticks)
                try: walk(e.virtual_entities())
                except Exception: pass
            elif t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'): emit(e, e.dxf.layer)
            elif t == 'HATCH': pass
    walk(doc.modelspace())
    return out, k


def sample(polys, step):
    pts = []; lab = []
    for layer, P in polys:
        for a, b in zip(P[:-1], P[1:]):
            L = np.linalg.norm(b - a); n = max(1, int(L / step))
            t = (np.arange(n) + 0.5) / n
            pts.append(a + (b - a) * t[:, None]); lab += [layer] * n
    return (np.concatenate(pts) if pts else np.zeros((0, 2))), lab


def fft_offset(A, B, cell):
    """translation t maximising the overlap of rasterised point sets (B ~ A + t), by FFT cross-correlation"""
    lo = np.minimum(A.min(0), B.min(0)); hi = np.maximum(A.max(0), B.max(0))
    span = hi - lo; n = (np.ceil(span / cell).astype(int) + 1) * 2
    n = np.minimum(n, 4096)
    cell = max(span[0] * 2 / n[0], span[1] * 2 / n[1], cell)
    def img(P):
        I = np.zeros((int(n[1]), int(n[0])))
        ij = ((P - lo) / cell).astype(int); ij = ij[(ij[:, 0] < n[0]) & (ij[:, 1] < n[1])]
        np.add.at(I, (ij[:, 1], ij[:, 0]), 1.0); return np.minimum(I, 1.0)
    FA = np.fft.rfft2(img(A)); FB = np.fft.rfft2(img(B))
    C = np.fft.irfft2(np.conj(FA) * FB, s=(int(n[1]), int(n[0])))
    y, x = np.unravel_index(np.argmax(C), C.shape)
    if x > n[0] / 2: x -= n[0]
    if y > n[1] / 2: y -= n[1]
    return np.array([x * cell, y * cell], float)


HATCH_LAYERS = {'cut_fill', 'surface_fill', 'symbolic_fill', 'room_fill'}


def our_segments(fn, vid):
    from rvtsheets.decode import Decoder
    from rvtsheets.viewdraw import ViewDrawer
    dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc); dr = vd.draw(vid)
    v = doc['views'][vid]
    O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
    polys = []
    # same paint order as viewsvg.body: a masking fill hides the ink painted before it (Revit's export leaves hidden lines out)
    lorder = {k: i for i, k in enumerate(('underlay', 'room_fill', 'symbolic_fill', 'cut_fill', 'surface_fill', 'projection', 'cut', 'symbolic', 'annotation_fill'))}
    lorder['mask'] = -1
    prims = dr['prims']
    has_order = any('order' in p for p in prims)
    key = (lambda p: (p.get('order', -2), lorder.get(p.get('layer'), 99))) if has_order else (lambda p: lorder.get(p.get('layer'), 99))
    for p in sorted(prims, key=key):
        L = p.get('layer') or p['t']
        if L == 'mask' and has_order and polys:
            from shapely.geometry import Polygon, LineString
            from shapely.ops import unary_union
            try: m = unary_union([Polygon(l).buffer(0) for l in p['loops'] if len(l) > 2])
            except Exception: continue
            if m.is_empty: continue
            out = []
            for L2, P in polys:
                ls = LineString(P) if len(P) > 1 else None
                if ls is None or not ls.intersects(m): out.append((L2, P)); continue
                g = ls.difference(m)
                for gg in getattr(g, 'geoms', [g]):
                    if gg.geom_type == 'LineString' and not gg.is_empty: out.append((L2, np.asarray(gg.coords)))
            polys = out
            continue
        if L in HATCH_LAYERS and not os.environ.get('CMP_HATCH'): continue                 # Revit's DXF holds fill patterns as HATCH entities (not compared): leave our hatch lines out too
        if p['t'] == 'line': polys.append((L, np.asarray(p['pts'], float)[:, :2]))
        elif p['t'] in ('segs',): polys += [(L, np.asarray(s, float)[:, :2]) for s in p['segs']]
        elif p['t'] == 'cut': polys += [(L, np.asarray(s, float)[:, :2]) for s in p['segs']]
    # Revit's export holds what the view shows: the crop region (datum heads / annotations may hang outside it)
    from rvtsheets.compose import crop_rect_uv
    cr = crop_rect_uv(v)
    if cr is not None:
        from shapely.geometry import LineString, box
        sc = v.get('scale') or 100; pad = 70.0 / 304.8 * sc
        inner = box(*cr); outer = box(cr[0] - pad, cr[1] - pad, cr[2] + pad, cr[3] + pad); out = []
        for L, P in polys:
            if len(P) < 2: continue
            g = LineString(P).intersection(outer if L in ('datum', 'text', 'annotation') else inner)
            for gg in getattr(g, 'geoms', [g]):
                if gg.geom_type == 'LineString' and not gg.is_empty: out.append((L, np.asarray(gg.coords)))
        polys = out
    return polys, v, O, X, Y


def main():
    fn, vid, dxf = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    ours, v, O, X, Y = our_segments(fn, vid)
    rv, k = dxf_segments(dxf)
    scale = v.get('scale') or 100
    step = 0.25 / 304.8 * scale; tol = float(os.environ.get('TOL_MM', '0.5')) / 304.8 * scale
    A, la = sample(ours, step)
    # Revit DXF of a view is in model coordinates (x, y world for plans); express in view u, v
    B3, lb = sample(rv, step)
    if v['kind'] == 'plan':
        B = np.stack([(B3[:, 0] - O[0]) * X[0] + (B3[:, 1] - O[1]) * X[1], (B3[:, 0] - O[0]) * Y[0] + (B3[:, 1] - O[1]) * Y[1]], 1)
    else:
        # sections/elevations/details: Revit's DXF is in view-plane coordinates about the world origin, (P.right, P.up) (2020 Residential
        # details: FFT registration found exactly O.right, O.up where it converged; on the eave detail it slid 0.04 ft along the roof)
        B = B3 - np.array([float(O @ X), float(O @ Y)])
    off = np.zeros(2)
    if '--register' in sys.argv and v['kind'] != 'plan' and '--fft' not in sys.argv: pass
    elif '--register' in sys.argv and len(A) and len(B):
        off = fft_offset(A, B, cell=step * 8)                     # 2 paper mm (a 0.25 ft floor misregistered 1:8 details by ~1")
        for _ in range(5):
            d, i = cKDTree(B).query(A + off); m = d < 20 * tol
            if m.sum() < 10: break
            off += np.median(B[i[m]] - (A[m] + off), 0)
    ta = cKDTree(A + off) if len(A) else None; tb = cKDTree(B) if len(B) else None
    da = tb.query(A + off)[0] if tb is not None and len(A) else np.array([])
    db = ta.query(B)[0] if ta is not None and len(B) else np.array([])
    res = {'view': vid, 'name': v['name'], 'scale': scale, 'ours_mm': len(A) * 0.25, 'revit_mm': len(B) * 0.25,
           'precision': float((da <= tol).mean()) if len(da) else 0, 'recall': float((db <= tol).mean()) if len(db) else 0, 'offset_ft': off.tolist()}
    per = collections.defaultdict(lambda: [0, 0])
    for l, d in zip(lb, db): per[l][0] += 1; per[l][1] += d <= tol
    res['recall_by_revit_layer'] = {l: [n, round(m / n, 3)] for l, (n, m) in sorted(per.items(), key=lambda kv: -kv[1][0])[:25]}
    perA = collections.defaultdict(lambda: [0, 0])
    for l, d in zip(la, da): perA[l][0] += 1; perA[l][1] += d <= tol
    res['precision_by_our_layer'] = {l: [n, round(m / n, 3)] for l, (n, m) in perA.items()}
    ml = os.environ.get('MISS_LAYER')
    if ml:                                                      # clusters of Revit samples of that layer without ink of ours (view coordinates, feet)
        sel = np.array([l == ml for l in lb]) & (db > tol)
        P = B[sel]
        if len(P):
            g = np.floor(P / float(os.environ.get('MISS_CELL', '3'))).astype(int); cl = collections.defaultdict(list)
            for q, c in zip(P, map(tuple, g)): cl[c].append(q)
            res['missing_clusters'] = [[len(v), np.round(np.min(v, 0), 1).tolist(), np.round(np.max(v, 0), 1).tolist()] for v in sorted(cl.values(), key=lambda v: -len(v))[:12]]
    el = os.environ.get('EXTRA_LAYER')
    if el:                                                      # clusters of our samples of that layer with no Revit ink nearby (view coordinates, feet)
        sel = np.array([l == el for l in la]) & (da > tol)
        P = (A + off)[sel]
        if len(P):
            g = np.floor(P / float(os.environ.get('MISS_CELL', '3'))).astype(int); cl = collections.defaultdict(list)
            for q, c in zip(P, map(tuple, g)): cl[c].append(q)
            res['extra_clusters'] = [[len(v), np.round(np.min(v, 0), 1).tolist(), np.round(np.max(v, 0), 1).tolist()] for v in sorted(cl.values(), key=lambda v: -len(v))[:12]]
    print(json.dumps(res, indent=1))


if __name__ == '__main__': main()
