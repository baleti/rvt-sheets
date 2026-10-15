"""Fill patterns -> explicit hatch segments clipped to a region (exact, renderer independent).
FillPattern grids (FillPatternElem.m_pFillPattern.m_gridsArr): angle, origin (u,v), deltas = (shift along the line, offset between lines),
segments (dash/space lengths along the line, empty = continuous). Drafting patterns (target 0) are sized on paper (feet of paper),
model patterns (target 1) in model feet. Region coordinates are view u,v in model feet; paper size = model * (1/scale)."""
import math
import numpy as np
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


def hatch(geom, pattern, scale, view_rot=0.0):
    """pattern dict (decode.fill_patterns) -> list of segments [[u0,v0],[u1,v1]] in view coordinates"""
    if geom is None or geom.is_empty or not pattern or pattern.get('solid'): return []
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
        # lines: o + j*(offset*nrm + shift*d) + t*d
        jc = float((np.array([cx, cy]) - o) @ nrm) / off
        n = int(R / off) + 2
        if 2 * n > MAX_LINES: n = MAX_LINES // 2
        segs = [s * k for s in g.get('segments') or []]
        lines = []
        for j in range(int(jc) - n, int(jc) + n + 1):
            base = o + j * (off * nrm + shift * d)
            tc = float((np.array([cx, cy]) - base) @ d)
            p0 = base + (tc - R) * d; p1 = base + (tc + R) * d
            if not segs:
                lines.append(LineString([tuple(p0), tuple(p1)]))
            else:
                per = sum(abs(s) for s in segs)
                if per <= 1e-12: continue
                t = math.floor((tc - R) / per) * per
                while t < tc + R:
                    for i, s in enumerate(segs):
                        L = abs(s)
                        if i % 2 == 0:                                  # dash (a zero-length dash is a dot)
                            q0 = base + t * d; q1 = base + (t + max(L, 1e-4 * k)) * d
                            lines.append(LineString([tuple(q0), tuple(q1)]))
                        t += L
        if not lines: continue
        cl = geom.intersection(MultiLineString(lines))
        for ls in getattr(cl, 'geoms', [cl]):
            if ls.is_empty or ls.geom_type != 'LineString': continue
            c = list(ls.coords)
            for a_, b_ in zip(c, c[1:]): out.append([list(a_), list(b_)])
    return out
