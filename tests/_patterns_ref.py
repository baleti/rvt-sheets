"""Fill patterns -> explicit hatch segments clipped to a region (exact, renderer independent).
FillPattern grids (FillPatternElem.m_pFillPattern.m_gridsArr): angle, origin (u,v), deltas = (shift along the line, offset between lines),
segments (dash/space lengths along the line, empty = continuous). Drafting patterns (target 0) are sized on paper (feet of paper),
model patterns (target 1) in model feet. Region coordinates are view u,v in model feet; paper size = model * (1/scale)."""
import math, os
import numpy as np
import shapely
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString
from shapely.ops import unary_union

MAX_LINES = 4000


def region(loops):
    """closed loops -> shapely (Multi)Polygon with even-odd holes"""
    polys = []
    for l in loops:
        if len(l) < 3: continue
        try:
            p = Polygon([tuple(q[:2]) for q in l])
            if not p.is_valid: p = p.buffer(0)
            if p.area > 1e-12: polys.append(p)
        except Exception: pass
    if not polys: return None
    # even-odd: symmetric difference of all loops
    g = polys[0]
    for p in polys[1:]: g = g.symmetric_difference(p)
    return g


WORLD_UV = None      # (u, v) of the world origin in the current view: model patterns (target != 0) keep their phase relative to it (Commercial 'Brick' parapet: head joints fall outside the 0.3 ft layer)
ANCHOR = None         # (unit normal, offset) set by ViewDrawer._wall_layers around the hatch of one layer strip
CLIP = None         # shapely geometry set by ViewDrawer.draw while drawing a cropped view: hatching stops at the crop (+5%)


MAX_DASHES = 600000
DOT_MM = 0.15          # a zero-length dash (stipple dot) is drawn as a 0.15 mm paper dash: with the round cap of the 0.1 mm pen Revit's dots (~0.3 mm) are matched; 1e-4 model ft made faint 0.1 mm specks
SKIPPED = __import__('collections').Counter()


def hatch(geom, pattern, scale, view_rot=0.0):
    """pattern dict (decode.fill_patterns) -> list of segments [[u0,v0],[u1,v1]] in view coordinates"""
    if geom is None or geom.is_empty or not pattern or pattern.get('solid'): return []
    if CLIP is not None:
        # 2020 Commercial 1:8 detail: surface and topography hatches over whole surfaces made 30 M segments (563 of 569 s)
        geom = geom.intersection(CLIP)
        if geom.is_empty: return []
    k0 = scale if pattern.get('target', 0) == 0 else 1.0
    minx, miny, maxx, maxy = geom.bounds
    # a hatch region that is huge compared with the pattern spacing would emit millions of segments (topography under a detail view):
    # keep the part within 2000 pattern lines of its centre (the sheet/crop clips the rest anyway)
    spacing = min([abs(g['offset']) * k0 for g in pattern.get('grids') or [] if abs(g['offset']) > 1e-9] or [1.0])
    if max(maxx - minx, maxy - miny) / spacing > 3000:
        from shapely.geometry import box
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2; r = 1500 * spacing
        geom = geom.intersection(box(cx - r, cy - r, cx + r, cy + r))
        if geom.is_empty: return []
    k = scale if pattern.get('target', 0) == 0 else 1.0           # drafting patterns: paper feet -> model feet
    out = []
    minx, miny, maxx, maxy = geom.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2; R = math.hypot(maxx - minx, maxy - miny) / 2 + 1e-9
    for g in pattern.get('grids') or []:
        a = g['angle'] + view_rot
        d = np.array([math.cos(a), math.sin(a)]); nrm = np.array([-d[1], d[0]])
        off = abs(g['offset']) * k; shift = g['shift'] * k
        if off <= 1e-12: continue
        o = np.array(g['origin'][:2], float) * k
        if WORLD_UV is not None and pattern.get('target', 0) != 0 and not view_rot: o = o + np.array(WORLD_UV)
        if ANCHOR is not None and pattern.get('target', 0) != 0:        # wall layer strip: the model pattern starts at the layer's face along the wall normal (Revit 'Brick' on the 0.3 ft parapet layer shows no head joints)
            n_, e_ = ANCHOR; o = o - n_ * float(o @ n_) + n_ * e_
        # lines: o + j*(offset*nrm + shift*d) + t*d
        jc = float((np.array([cx, cy]) - o) @ nrm) / off
        n = int(R / off) + 2
        if 2 * n > MAX_LINES: n = MAX_LINES // 2
        segs = [s * k for s in g.get('segments') or []]
        ends = []                                                    # (p0, p1) pairs, built into LineStrings in one vectorised call below
        js = np.arange(int(jc) - n, int(jc) + n + 1)
        if not segs:
            bases = o[None, :] + js[:, None] * (off * nrm + shift * d)[None, :]
            tcs = (np.array([cx, cy])[None, :] - bases) @ d
            p0 = bases + (tcs - R)[:, None] * d[None, :]; p1 = bases + (tcs + R)[:, None] * d[None, :]
            lines_arr = np.stack([p0, p1], 1)
        else:
            per = sum(abs(s_) for s_ in segs)
            if per <= 1e-12: continue
            if len(js) * (2 * R / per + 2) * ((len(segs) + 1) // 2) > MAX_DASHES:        # a fine stipple over a big region (1:16 plan floor: 'Sand' millions of dots, 6 GB): not generated
                SKIPPED['dashes'] += 1
                if os.environ.get('RVT_STIPPLE', '1') == '1' and pattern.get('target', 0) == 0: return stipple(geom, scale)
                return []
            for j in js:
                base = o + j * (off * nrm + shift * d)
                tc = float((np.array([cx, cy]) - base) @ d)
                t = math.floor((tc - R) / per) * per
                while t < tc + R:
                    for i, s_ in enumerate(segs):
                        L = abs(s_)
                        if i % 2 == 0:                                  # dash (a zero-length dash is a dot)
                            ends.append((base + t * d, base + (t + (L if L > 1e-6 * k else DOT_MM / 304.8 * scale)) * d))
                        t += L
            lines_arr = np.asarray(ends, float).reshape(-1, 2, 2)
        if not len(lines_arr): continue
        lines = shapely.linestrings(lines_arr)
        cl = geom.intersection(shapely.multilinestrings(lines))
        for ls in getattr(cl, 'geoms', [cl]):
            if ls.is_empty or ls.geom_type != 'LineString': continue
            c = list(ls.coords)
            for a_, b_ in zip(c, c[1:]): out.append([list(a_), list(b_)])
    return out


STIPPLE_PER_MM2 = 0.05      # Revit thins very fine stipples (Sand: 0.25 dots / mm2 on paper by definition) to about 0.05 dots / mm2 in its 1:96 plan export (speckled room floors)


def stipple(geom, scale, seed=7):
    """sparse deterministic random dots over a region: stands for a drafting stipple too fine to generate dash by dash"""
    minx, miny, maxx, maxy = geom.bounds
    area_mm2 = geom.area * (304.8 / scale) ** 2
    n = int(min(area_mm2 * STIPPLE_PER_MM2, 150000))
    if n < 1: return []
    rng = np.random.default_rng(int(abs(minx * 1000 + miny * 7000)) % (2 ** 31) + seed)
    m = int(n * (geom.envelope.area / max(geom.area, 1e-12)) * 1.1) + 10
    pts = np.column_stack([rng.uniform(minx, maxx, m), rng.uniform(miny, maxy, m)])
    keep = shapely.contains_xy(geom, pts[:, 0], pts[:, 1])
    pts = pts[keep][:n]
    d = 0.2 / 304.8 * scale
    return [[[float(x), float(y)], [float(x + d), float(y)]] for x, y in pts]
