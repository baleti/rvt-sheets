"""Hidden-line removal by depth buffer (numba). View coordinates: u, v on paper (feet of model), w = depth towards the viewer
(larger w = nearer the eye). A segment sample is visible when no triangle in front of it covers its pixel."""
import os
import numpy as np
try:
    from numba import njit
except ImportError:                                   # pure-python fallback (slow)
    def njit(*a, **k):
        def d(f): return f
        return d if not (a and callable(a[0])) else a[0]


@njit(cache=True)
def _raster(tris, W, H, u0, v0, px, zb):
    """tris: (n,3,3) [u,v,w]; zb: (H,W) max-w buffer (nearest surface)"""
    for t in range(tris.shape[0]):
        x0 = (tris[t, 0, 0] - u0) / px; y0 = (tris[t, 0, 1] - v0) / px; z0 = tris[t, 0, 2]
        x1 = (tris[t, 1, 0] - u0) / px; y1 = (tris[t, 1, 1] - v0) / px; z1 = tris[t, 1, 2]
        x2 = (tris[t, 2, 0] - u0) / px; y2 = (tris[t, 2, 1] - v0) / px; z2 = tris[t, 2, 2]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12: continue
        xmin = max(int(np.floor(min(x0, x1, x2))), 0); xmax = min(int(np.ceil(max(x0, x1, x2))), W - 1)
        ymin = max(int(np.floor(min(y0, y1, y2))), 0); ymax = min(int(np.ceil(max(y0, y1, y2))), H - 1)
        # slope-scaled depth bias: a face steep to the view (roof slopes in elevations) changes depth by more than eps across the 3x3
        # neighbourhood _visible looks at, which hid its own edges (ridges, eaves). Push each face back by ~2 pixels of its gradient.
        gx = ((z0 - z2) * (y1 - y2) - (z1 - z2) * (y0 - y2)) / den
        gy = ((z1 - z2) * (x0 - x2) - (z0 - z2) * (x1 - x2)) / den
        bias = min(2.0 * np.sqrt(gx * gx + gy * gy), 0.5)
        for yy in range(ymin, ymax + 1):
            py = yy + 0.5
            for xx in range(xmin, xmax + 1):
                pxx = xx + 0.5
                a = ((y1 - y2) * (pxx - x2) + (x2 - x1) * (py - y2)) / den
                b = ((y2 - y0) * (pxx - x2) + (x0 - x2) * (py - y2)) / den
                c = 1.0 - a - b
                if a < -1e-6 or b < -1e-6 or c < -1e-6: continue
                z = a * z0 + b * z1 + c * z2 - bias
                if z > zb[yy, xx]: zb[yy, xx] = z


@njit(cache=True)
def _visible(segs, n_samp, u0, v0, px, zb, eps, out):
    """segs: (m,2,3); out: (m, n_samp) bool visibility of samples"""
    H = zb.shape[0]; W = zb.shape[1]
    for s in range(segs.shape[0]):
        for k in range(n_samp):
            t = (k + 0.5) / n_samp
            u = segs[s, 0, 0] + t * (segs[s, 1, 0] - segs[s, 0, 0])
            v = segs[s, 0, 1] + t * (segs[s, 1, 1] - segs[s, 0, 1])
            w = segs[s, 0, 2] + t * (segs[s, 1, 2] - segs[s, 0, 2])
            xx = int((u - u0) / px); yy = int((v - v0) / px)
            vis = True
            # nearest surface over a 3x3 neighbourhood: an edge running exactly under a nearer surface's outline (e.g. under a cut
            # outline) is hidden; an edge on its own face is not (its face has the same depth, within eps)
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    X = xx + dx; Y = yy + dy
                    if X < 0 or Y < 0 or X >= W or Y >= H: continue
                    if zb[Y, X] > w + eps: vis = False
            out[s, k] = vis


class DepthBuffer:
    def __init__(self, umin, vmin, umax, vmax, px):
        self.u0 = umin - 2 * px; self.v0 = vmin - 2 * px; self.px = px
        self.W = int((umax - umin) / px) + 5; self.H = int((vmax - vmin) / px) + 5
        if self.W * self.H > 64e6:                         # cap memory: coarser pixels
            f = (self.W * self.H / 64e6) ** 0.5
            self.px = px * f; self.W = int((umax - umin) / self.px) + 5; self.H = int((vmax - vmin) / self.px) + 5
            self.u0 = umin - 2 * self.px; self.v0 = vmin - 2 * self.px
        self.zb = np.full((self.H, self.W), -1e30)

    def add(self, tris):
        if not len(tris): return
        tris = np.ascontiguousarray(tris, dtype=np.float64)
        try:
            import rvt_fast
            if os.environ.get('RVT_NO_RUST_RASTER') != '1' and rvt_fast.hlr_raster(tris, self.W, self.H, self.u0, self.v0, self.px, self.zb): return    # bit-identical to _raster, row bands in parallel
        except Exception: pass
        _raster(tris, self.W, self.H, self.u0, self.v0, self.px, self.zb)

    def visible_parts(self, segs, eps):
        """segs (m,2,3) -> list of visible sub-segments [(p0, p1)] in uvw"""
        segs = np.ascontiguousarray(segs, dtype=np.float64)
        if not len(segs): return []
        L = np.linalg.norm(segs[:, 1, :2] - segs[:, 0, :2], axis=1)
        n = int(min(max(4, (L.max() / self.px) * 1.5), 400))
        vis = np.zeros((len(segs), n), dtype=np.bool_)
        _visible(segs, n, self.u0, self.v0, self.px, self.zb, eps, vis)
        out = []
        for s in range(len(segs)):
            row = vis[s]
            if row.all(): out.append((segs[s, 0], segs[s, 1])); continue
            if not row.any(): continue
            k = 0
            while k < n:
                if row[k]:
                    j = k
                    while j + 1 < n and row[j + 1]: j += 1
                    t0 = k / n; t1 = (j + 1) / n
                    out.append((segs[s, 0] + t0 * (segs[s, 1] - segs[s, 0]), segs[s, 0] + t1 * (segs[s, 1] - segs[s, 0])))
                    k = j + 1
                else: k += 1
        return out
