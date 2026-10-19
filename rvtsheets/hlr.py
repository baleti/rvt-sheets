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
def _raster_rgba(tris, x_off, y_off, u0, v0, px, zb, img, rgba, eps):
    """paint the triangles (n,3,3) [u,v,w] into img (h,w,4) (a window starting at pixel x_off, y_off of the depth buffer) with rgba where
    the triangle's own depth is the nearest surface of its pixel (within eps)"""
    H = zb.shape[0]; W = zb.shape[1]; h = img.shape[0]; w = img.shape[1]
    for t in range(tris.shape[0]):
        x0 = (tris[t, 0, 0] - u0) / px; y0 = (tris[t, 0, 1] - v0) / px; z0 = tris[t, 0, 2]
        x1 = (tris[t, 1, 0] - u0) / px; y1 = (tris[t, 1, 1] - v0) / px; z1 = tris[t, 1, 2]
        x2 = (tris[t, 2, 0] - u0) / px; y2 = (tris[t, 2, 1] - v0) / px; z2 = tris[t, 2, 2]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12: continue
        xmin = max(int(np.floor(min(x0, x1, x2))), x_off); xmax = min(int(np.ceil(max(x0, x1, x2))), x_off + w - 1, W - 1)
        ymin = max(int(np.floor(min(y0, y1, y2))), y_off); ymax = min(int(np.ceil(max(y0, y1, y2))), y_off + h - 1, H - 1)
        for yy in range(ymin, ymax + 1):
            py = yy + 0.5
            for xx in range(xmin, xmax + 1):
                pxx = xx + 0.5
                a = ((y1 - y2) * (pxx - x2) + (x2 - x1) * (py - y2)) / den
                b = ((y2 - y0) * (pxx - x2) + (x0 - x2) * (py - y2)) / den
                c = 1.0 - a - b
                if a < -1e-6 or b < -1e-6 or c < -1e-6: continue
                z = a * z0 + b * z1 + c * z2
                if z + eps >= zb[yy, xx]:
                    for q in range(4): img[yy - y_off, xx - x_off, q] = rgba[q]


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

    def paint(self, groups, eps):
        """groups: [(tris (n,3,3) uvw, (r, g, b, a))] painted back to front onto a transparent window of the depth buffer wherever they are the nearest
        surface: (png bytes, (u0, v0, u1, v1)) or None. Later groups paint over earlier ones."""
        groups = [(np.ascontiguousarray(t, dtype=np.float64), c) for t, c in groups if len(t)]
        if not groups: return None
        allt = np.concatenate([t for t, _ in groups])
        xs = (allt[:, :, 0] - self.u0) / self.px; ys = (allt[:, :, 1] - self.v0) / self.px
        x0 = max(int(np.floor(xs.min())), 0); x1 = min(int(np.ceil(xs.max())) + 1, self.W); y0 = max(int(np.floor(ys.min())), 0); y1 = min(int(np.ceil(ys.max())) + 1, self.H)
        if x1 <= x0 or y1 <= y0: return None
        img = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
        for t, c in groups: _raster_rgba(t, x0, y0, self.u0, self.v0, self.px, self.zb, img, np.asarray(c, dtype=np.uint8), eps)
        if not img[:, :, 3].any(): return None
        import io
        from PIL import Image
        buf = io.BytesIO(); Image.fromarray(img[::-1]).save(buf, 'PNG', optimize=False, compress_level=3)       # v grows upwards, image rows downwards
        return buf.getvalue(), (self.u0 + x0 * self.px, self.v0 + y0 * self.px, self.u0 + x1 * self.px, self.v0 + y1 * self.px)

    def visible_parts(self, segs, eps):
        """segs (m,2,3) -> list of visible sub-segments [(p0, p1)] in uvw"""
        segs = np.ascontiguousarray(segs, dtype=np.float64)
        if not len(segs): return []
        L = np.linalg.norm(segs[:, 1, :2] - segs[:, 0, :2], axis=1)
        n = int(min(max(4, (L.max() / self.px) * 1.5), 400))
        vis = np.zeros((len(segs), n), dtype=np.bool_)
        ok = False
        try:
            import rvt_fast
            ok = os.environ.get('RVT_NO_RUST_RASTER') != '1' and rvt_fast.hlr_visible(segs, n, self.u0, self.v0, self.px, self.zb, eps, vis)     # bit-identical to _visible, segments in parallel
        except Exception: pass
        if not ok: _visible(segs, n, self.u0, self.v0, self.px, self.zb, eps, vis)
        out = []
        allv = vis.all(1); anyv = vis.any(1)
        part = np.nonzero(anyv & ~allv)[0]
        runs = {}
        if len(part):                                   # run starts / ends of the partially visible segments, in row chunks (a 1:16 plan has millions of edges x 400 samples)
            CH = 4096
            for c0 in range(0, len(part), CH):
                rows_ = part[c0:c0 + CH]
                pad = np.zeros((len(rows_), n + 2), dtype=np.int8); pad[:, 1:-1] = vis[rows_]
                dd = np.diff(pad, axis=1)
                rs, cs = np.nonzero(dd == 1); re_, ce = np.nonzero(dd == -1)
                for r_, c_a, c_b in zip((rs + c0).tolist(), cs.tolist(), ce.tolist()): runs.setdefault(r_, []).append((c_a, c_b))
        pidx = {int(sg): k for k, sg in enumerate(part)}
        for s in range(len(segs)):
            if allv[s]: out.append((segs[s, 0], segs[s, 1])); continue
            if not anyv[s]: continue
            d = segs[s, 1] - segs[s, 0]
            for k0, k1 in runs[pidx[s]]:
                out.append((segs[s, 0] + (k0 / n) * d, segs[s, 0] + (k1 / n) * d))
        return out
