"""Polygon construction from offset area-boundary curves."""

import math

import numpy as np
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union


def boundary_polygons(lines, arcs):
    """Return polygons enclosed by offset lines and arcs (coordinates in feet).

    Lines are (origin_xy, dir_xy, t0, t1, offset); arcs are
    (center_xy, radius, xvec_xy, yvec_xy, t0, t1, offset).
    """
    shifted = max((abs(curve[-1]) for curve in lines + arcs), default=0.0)
    ext = shifted + 0.05 if shifted else 0.0
    segs = []
    for center, radius, xvec, yvec, t0, t1, offset in arcs:
        ce = np.asarray(center, float)
        xv = np.asarray(xvec, float)
        yv = np.asarray(yvec, float)
        rad = radius + offset * (1.0 if xv[0] * yv[1] - xv[1] * yv[0] > 0 else -1.0)
        ts = np.linspace(t0, t1, max(8, int(abs(t1 - t0) / 0.05)))
        pts = [ce + rad * (math.cos(t) * xv + math.sin(t) * yv) for t in ts]
        if offset:
            u0 = pts[0] - pts[1]
            u1 = pts[-1] - pts[-2]
            pts = [pts[0] + u0 / (np.linalg.norm(u0) or 1.0)] + pts + [
                pts[-1] + u1 / (np.linalg.norm(u1) or 1.0)
            ]
        segs.append(LineString([tuple(np.round(q, 5)) for q in pts]))
    for origin, direction, t0, t1, offset in lines:
        d = np.asarray(direction, float)
        o = np.asarray(origin, float) + offset * np.array([d[1], -d[0]])
        segs.append(LineString([
            tuple(np.round(o + d * (t0 - ext), 5)),
            tuple(np.round(o + d * (t1 + ext), 5)),
        ]))
    return list(polygonize(unary_union(segs))) if segs else []
