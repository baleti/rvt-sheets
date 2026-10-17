"""Shaded 3D view (perspective or orthographic) as an image for sheets: pinhole camera from the view's origin/direction/up and the crop box
(perspective views store the crop as tangents at unit distance: bounds = [[right, left], [top, bottom], [far, near]] -> field of view),
per-triangle material colours, Lambert shading with one sun + ambient, numba z-buffer, sky gradient background. Output: PNG bytes.
Not a Revit-exact renderer (no shadows, textures, entourage): a faithful-colour massing view like Revit's 'Shaded' style."""
import io, math
import numpy as np
from numba import njit


@njit(cache=True)
def _raster(tx, ty, tz, col, alpha, W, H, zb, img):
    """tx,ty (n,3) pixel coordinates, tz (n,3) 1/depth, col (n,3) uint8 -> img (H,W,3), zb (H,W) max 1/depth"""
    for t in range(tx.shape[0]):
        x0, x1, x2 = tx[t, 0], tx[t, 1], tx[t, 2]; y0, y1, y2 = ty[t, 0], ty[t, 1], ty[t, 2]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12: continue
        xmin = max(int(math.floor(min(x0, x1, x2))), 0); xmax = min(int(math.ceil(max(x0, x1, x2))), W - 1)
        ymin = max(int(math.floor(min(y0, y1, y2))), 0); ymax = min(int(math.ceil(max(y0, y1, y2))), H - 1)
        for yy in range(ymin, ymax + 1):
            py = yy + 0.5
            for xx in range(xmin, xmax + 1):
                px = xx + 0.5
                a = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / den
                b = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / den
                c = 1.0 - a - b
                if a < -1e-9 or b < -1e-9 or c < -1e-9: continue
                z = a * tz[t, 0] + b * tz[t, 1] + c * tz[t, 2]
                if z > zb[yy, xx]:
                    al = alpha[t]
                    if al >= 0.999:
                        zb[yy, xx] = z
                        img[yy, xx, 0] = col[t, 0]; img[yy, xx, 1] = col[t, 1]; img[yy, xx, 2] = col[t, 2]
                    else:                                              # transparent (glass): blend over what is there, keep the depth behind
                        img[yy, xx, 0] = np.uint8(al * col[t, 0] + (1 - al) * img[yy, xx, 0])
                        img[yy, xx, 1] = np.uint8(al * col[t, 1] + (1 - al) * img[yy, xx, 1])
                        img[yy, xx, 2] = np.uint8(al * col[t, 2] + (1 - al) * img[yy, xx, 2])


def render(tris, colors, alphas, eye, right, up, fwd, tan_x, tan_y, width_px, perspective=True, ortho_half=None, centre=(0.0, 0.0), sun=(-0.4, -0.5, 0.75),
           sky=((176, 197, 218), (232, 238, 244)), ground=(150, 150, 150)):
    """tris (n,3,3) world feet, colors (n,3) 0..255 base colours. tan_x/tan_y: half field of view tangents (perspective) or None.
    Returns (png bytes, width, height). Camera looks along fwd; right/up orthonormal."""
    if perspective:
        W = int(width_px); H = max(1, int(round(W * tan_y / tan_x)))
    else:
        W = int(width_px); H = max(1, int(round(W * ortho_half[1] / ortho_half[0])))
    rel = tris - eye
    X = rel @ right; Y = rel @ up; D = rel @ fwd                                  # camera coordinates
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1); ln[ln == 0] = 1; n = n / ln[:, None]
    to_eye = -(rel.mean(1)); facing = (n * to_eye).sum(1)
    n[facing < 0] *= -1                                                          # two-sided shading
    L = np.asarray(sun, float); L = L / np.linalg.norm(L)
    shade = 0.45 + 0.55 * np.clip((n * L).sum(1), 0, 1) ** 0.8                  # ambient + diffuse
    col = np.clip(colors * shade[:, None], 0, 255).astype(np.uint8)
    # near-plane clipping: drop triangles with any vertex behind 0.1 ft (cheap; entourage rarely crosses the eye)
    keep = (D > 0.1).all(1)
    X, Y, D, col, alphas = X[keep], Y[keep], D[keep], col[keep], np.asarray(alphas, float)[keep]
    order = np.argsort(alphas < 0.999, kind='stable')                            # opaque first, transparent last
    X, Y, D, col, alphas = X[order], Y[order], D[order], col[order], alphas[order]
    if perspective:
        px = ((X / D - centre[0]) / tan_x * 0.5 + 0.5) * W; py = (0.5 - (Y / D - centre[1]) / tan_y * 0.5) * H; iz = 1.0 / D
    else:
        px = ((X - centre[0]) / ortho_half[0] * 0.5 + 0.5) * W; py = (0.5 - (Y - centre[1]) / ortho_half[1] * 0.5) * H; iz = 1.0 / np.maximum(D, 0.1)
    zb = np.full((H, W), -1.0); img = np.zeros((H, W, 3), np.uint8)
    # background: sky gradient (top -> horizon), ground below the horizon when the camera is level-ish
    t = np.linspace(0, 1, H)[:, None, None]
    img[:] = (np.array(sky[0]) * (1 - t) + np.array(sky[1]) * t).astype(np.uint8)
    if len(px):
        _raster(np.ascontiguousarray(px), np.ascontiguousarray(py), np.ascontiguousarray(iz), np.ascontiguousarray(col), np.ascontiguousarray(alphas), W, H, zb, img)
    from PIL import Image
    bio = io.BytesIO(); Image.fromarray(img).save(bio, 'PNG', optimize=False, compress_level=3)
    return bio.getvalue(), W, H


SITE_CATS = {-2001340, -2001360}                                   # topography, planting?: green when no material colour


def view_image(drawer, vid, width_px=1600, max_tris=2_000_000):
    """shaded image of 3D view `vid` through the ViewDrawer machinery: (png, w, h)"""
    got = collect(drawer, vid, max_tris)
    if got is None: return None
    T, C, A, (O, X, Y, Z, c, persp), _K = got
    b = c.get('bounds') or [[1, -1], [1, -1], [0, 0]]
    if persp:
        # crop bounds of a perspective view = tangents on the unit-distance plane: [[right, left], [top, bottom], ...]
        pd = c.get('proj_dist') or 0.1                           # distance of the crop plane from the eye (feet)
        png, w, h = render(T, C, A, O, X, Y, Z, (b[0][0] - b[0][1]) / 2 / pd, (b[1][0] - b[1][1]) / 2 / pd, width_px, True,
                           centre=((b[0][0] + b[0][1]) / 2 / pd, (b[1][0] + b[1][1]) / 2 / pd))
    else:
        half = ((b[0][0] - b[0][1]) / 2, (b[1][0] - b[1][1]) / 2)
        png, w, h = render(T, C, A, O, X, Y, Z, None, None, width_px, False, ortho_half=half)
    return png, w, h


def collect(drawer, vid, max_tris=2_000_000):
    """world-space triangles of 3D view `vid` with colours, alphas and category ids, and the camera: (T, C, A, (O, X, Y, Z, crop, persp), K) or None"""
    import collections
    cc = getattr(drawer, '_collect_cache', None)
    if cc and cc[0] == (vid, max_tris): return cc[1]            # shaded image and edge overlay of one view share one collection
    from .scene import Walker, ViewCtx
    doc = drawer.doc; v = doc['views'][vid]; ev = drawer.vis.effective(v)
    O, X, Y, Z = drawer.frame(v)
    Z = -Z                                    # stored view direction points from the target towards the eye; the camera looks along -dir
    c = v.get('crop') or {}
    persp = c.get('proj_method') == 2
    ctx = ViewCtx(Z, detail=ev.get('detail_level') or 2, kind='3d', scale=1)
    W = Walker(drawer.f, ctx); W.is_2d = lambda e: False; W.invisible_gs = set()
    mats = drawer.materials(); elems = drawer.vis.elements(vid)
    T = []; C = []; A = []; K = []
    for eid in elems:
        info = drawer.vis.info.info[eid]
        if info['cls'] in ('Grid', 'Level', 'RefPlane', 'IndependentTag', 'RoomTag', 'LinearDimString', 'TextNote', 'InteriorElev', 'InteriorElevArrow', 'Section') or info['cls'] in ('RoomElem',): continue
        try: pieces = W.walk_record(eid)
        except Exception: continue
        cid = info['cat']
        base = (drawer.doc['categories'].get(cid) or {}).get('proj') or {}
        if not pieces['solids']:
            # no own B-rep solids (topography polymesh, family instances whose geometry sits in the symbol): the reader's element mesh
            try:
                import rvt_elemmesh as E
                m = E.element_mesh(drawer.f.g, eid); tr = np.asarray(m.get('tris') or [], float).reshape(-1, 3, 3)
            except Exception: tr = np.zeros((0, 3, 3))
            if len(tr):
                col = (110, 150, 105) if cid in SITE_CATS else (base.get('color') if base.get('color') and any(base.get('color')) else (170, 170, 170))
                T.append(tr); C.append(np.tile(np.asarray(col, float), (len(tr), 1))); A.append(np.ones(len(tr))); K.append(np.full(len(tr), cid))
            continue
        for s in pieces['solids']:
            if not drawer.drawable_gs(s.get('gs')): continue
            gcat = (drawer.doc['gstyles'].get(s.get('gs')) or {}).get('cat')
            if 'light source' in str((drawer.doc['categories'].get(gcat) or {}).get('name') or '').lower(): continue        # light cones are not drawn
            t = drawer._tess(s)
            if t is None or not len(t[0]): continue
            tris = t[0]; frs = t[2] if len(t) > 2 else None
            cols = np.empty((len(tris), 3)); al = np.ones(len(tris))
            gm = (drawer.doc['gstyles'].get(s.get('gs')) or {}).get('material')
            fallback = base.get('color')
            if not fallback or not any(fallback) or not base.get('material') in (None, -1) and False: fallback = (190, 190, 190)       # category pens are black: neutral grey
            if cid in SITE_CATS: fallback = (110, 150, 105)
            for i in range(len(tris)):
                m = None
                if frs is not None and i < len(frs) and frs[i] is not None:
                    try: m = mats.get(int(frs[i]))
                    except Exception: m = None
                if m is None and gm not in (None, -1): m = mats.get(gm)
                if m and 'light source' in str(m.get('name')).lower(): al[i] = 0.0; cols[i] = (0, 0, 0); continue        # light cones: not drawn
                col = (m or {}).get('color')
                cols[i] = col if col and any(col) else fallback
                tr = (m or {}).get('transparency') or 0
                if tr: al[i] = max(0.15, 1 - float(tr))
            keep = al > 0
            if not keep.any(): continue
            T.append(tris[keep]); C.append(cols[keep]); A.append(al[keep]); K.append(np.full(int(keep.sum()), cid))
    if not T: return None
    T = np.concatenate(T); C = np.concatenate(C); A = np.concatenate(A); K = np.concatenate(K)
    if len(T) > max_tris: sel = np.random.default_rng(0).choice(len(T), max_tris, replace=False); T, C, A, K = T[sel], C[sel], A[sel], K[sel]
    res = (T, C, A, (O, X, Y, Z, c, persp), K)
    drawer._collect_cache = ((vid, max_tris), res)
    return res


def plan_image(drawer, vid, width_px=2400, max_tris=2_000_000):
    """shaded top view of a plan with a shaded visual style (Revit fills surfaces with their material colours, e.g. the Commercial site plan):
    (png, w, h) covering the view's crop rectangle, or None"""
    got = collect(drawer, vid, max_tris)
    if got is None: return None
    T, C, A, (O, X, Y, Z, c, persp), K = got
    b = c.get('bounds')
    if not b or not len(T): return None
    # collect() flips the stored direction for 3D views (which point at the eye); a plan's already looks down -Z after the same flip
    eye = np.array([O[0], O[1], float(T[:, :, 2].max()) + 10.0]); fwd = np.array([0.0, 0.0, -1.0])
    half = ((b[0][0] - b[0][1]) / 2, (b[1][0] - b[1][1]) / 2); ctr = ((b[0][0] + b[0][1]) / 2, (b[1][0] + b[1][1]) / 2)
    png, w, h = render(T, C, A, eye, X, Y, fwd, None, None, width_px, False, ortho_half=half, centre=ctr,
                       sky=((255, 255, 255), (255, 255, 255)))
    return png, w, h


def is_shaded_plan(v):
    """plan drawn with a shaded style (ViewDisplayMgr.m_model.m_surfaces 3..6)"""
    return v.get('kind') == 'plan' and ((v.get('display') or {}).get('m_model') or {}).get('m_surfaces') in (3, 4, 5, 6)


def is_shaded(v):
    """3D view drawn with a shaded style (ViewDisplayMgr.m_model.m_surfaces: 2 = hidden line, 4 = shading / realistic)"""
    return v.get('kind') == '3d' and ((v.get('display') or {}).get('m_model') or {}).get('m_surfaces') in (3, 4, 5, 6)


def view_svg(drawer, vid, width_px=1600):
    """standalone drawing of a shaded 3D view: an SVG holding the shaded image at the crop's aspect (paper mm 200 wide)"""
    import base64
    r = view_image(drawer, vid, width_px)
    if not r: return None
    png, w, h = r; mm = 200.0; hh = mm * h / w
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%.1fmm" height="%.1fmm" viewBox="0 0 %.3f %.3f"><rect width="100%%" height="100%%" fill="#fff"/>'
            '<image x="0" y="0" width="%.3f" height="%.3f" href="data:image/png;base64,%s" preserveAspectRatio="none"/></svg>\n' % (mm, hh, mm, hh, mm, hh, base64.b64encode(png).decode()))


def persp_lines(drawer, vid, width_px=1600, max_tris=2_000_000):
    """hidden-line drawing of a perspective 3D view (Revit's 'Hidden Line' style, e.g. a section perspective): the visible feature and
    silhouette edges of the view's geometry, clipped by an active section box. Returns (segments, crop) with segments = [(p0, p1, pen)] in the
    tangent plane (x / depth, y / depth), crop = (xmin, ymin, xmax, ymax) of the crop region in the same units, or None.
    Hidden-line removal is the ordinary depth buffer with w = 1 / depth: perspective maps planes to planes and lines to lines in (x/d, y/d, 1/d)."""
    from .viewdraw import _feature_edges, _silhouette_edges, _clip_tris_halfspace
    from .hlr import DepthBuffer
    got = collect(drawer, vid, max_tris)
    if got is None: return None
    T, _C, _A, (O, X, Y, Z, c, persp), K = got
    v = drawer.doc['views'][vid]
    sb = v.get('section_box') or {}
    if sb.get('on'):                                              # section box: keep what lies inside it (triangles are cut at its planes)
        o = np.asarray(sb['origin'], float); B = np.asarray(sb['basis'], float)
        for i in range(3):
            hi, lo = sb['bounds'][i]
            n = B[i]
            T = _clip_tris_halfspace(T, n, float(o @ n + hi)); T = _clip_tris_halfspace(T, -n, float(-(o @ n + lo)))
            if not len(T): return [], None
        K = np.zeros(len(T), int)                                  # (clipping loses the per-triangle category: pens fall back to the default)
    rel = T - O
    Xc = rel @ X; Yc = rel @ Y; Dc = rel @ Z
    keep = (Dc > 0.1).all(1)
    Xc, Yc, Dc, Tw = Xc[keep], Yc[keep], Dc[keep], T[keep]
    if not len(Tw): return [], None
    P = np.stack([Xc / Dc, Yc / Dc, 1.0 / Dc], axis=2)            # (n,3,3): tangent x, tangent y, 1/depth
    b = c['bounds']; pd = c.get('proj_dist') or 0.1
    crop = (b[0][1] / pd, b[1][1] / pd, b[0][0] / pd, b[1][0] / pd)
    # edge candidates: B-rep / sharp edges (world space, mapped through the same projection) plus silhouettes (opposite facing in the image)
    def proj(E):
        r = E - O
        d = r @ Z
        return np.stack([(r @ X) / d, (r @ Y) / d, 1.0 / d], axis=-1)
    Ew = _feature_edges(Tw)
    ok = ((Ew - O) @ Z > 0.1).all(1) if len(Ew) else np.zeros(0, bool)
    E1 = proj(Ew[ok]) if ok.any() else np.zeros((0, 2, 3))
    E2 = _silhouette_edges(P)
    E = np.concatenate([E1, E2]) if len(E2) else E1
    if not len(E): return [], crop
    px = max((crop[2] - crop[0]), (crop[3] - crop[1])) / width_px
    db = DepthBuffer(crop[0], crop[1], crop[2], crop[3], px)
    db.add(P)
    eps = 0.5e-4
    vis = db.visible_parts(E, eps)
    pens = (drawer.doc.get('pens') or {}).get('perspective') or []
    pen_mm = pens[1] if len(pens) > 1 else 0.18
    return [(p0[:2], p1[:2], pen_mm) for p0, p1 in vis], crop
