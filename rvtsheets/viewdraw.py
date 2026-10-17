"""Stage 3/4: draw the model content of a plan / section / elevation view as 2D primitives in VIEW coordinates
(u, v = model feet along the view's right / up vectors from the view origin).
Pipeline per element: visibility -> saved graphics walked for this view (scene.Walker) -> solids tessellated (reader rvt_mesh) ->
clipped to the view depth range -> cut regions at the cut plane + projected feature edges with hidden-line removal (hlr.DepthBuffer)
-> symbolic 2D curves projected -> styles resolved (style.Resolver)."""
import math, collections, time, os, sys
import numpy as np
from .reader import INVALID, ob, ob as ob_, path
IN = 1 / 12.0
from .scene import Walker, ViewCtx
from .hlr import DepthBuffer
from .style import Resolver
from .visibility import Visibility
from . import patterns, gfx
from .visibility import CAT_TYPES, PHASE_IDX
from . import gfx

FEATURE_ANGLE = math.radians(20)
UNOBSCURED_CATS = {-2009000, -2009003, -2009009, -2009016, -2009017}     # structural rebar, area/path reinforcement, fabric (?)
NO_SOLID_CLASSES = {'RoomElem', 'AreaElem', 'ZoneElement', 'MassLevelData'}


def _clip_tris_halfspace(T, n, d):
    """keep the part of triangles T (k,3,3) with x.n <= d"""
    if not len(T): return T
    s = T @ n - d                                  # (k,3)
    inside = s <= 1e-9
    allin = inside.all(1); none = ~inside.any(1)
    out = [T[allin]]
    part = ~allin & ~none
    for t, ss, ins in zip(T[part], s[part], inside[part]):
        poly = []
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]; sa, sb = ss[i], ss[(i + 1) % 3]
            if sa <= 1e-9: poly.append(a)
            if (sa <= 1e-9) != (sb <= 1e-9):
                poly.append(a + (b - a) * (sa / (sa - sb)))
        for i in range(1, len(poly) - 1): out.append(np.array([[poly[0], poly[i], poly[i + 1]]]))
    return np.concatenate([o for o in out if len(o)]) if any(len(o) for o in out) else T[:0]


def _plane_section(T, n, d):
    """segments where triangles T cross the plane x.n = d"""
    s = T @ n - d
    segs = []
    for t, ss in zip(T, s):
        if (ss > 0).all() or (ss < 0).all(): continue
        pts = []
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]; sa, sb = ss[i], ss[(i + 1) % 3]
            if sa == 0: pts.append(a)
            elif (sa < 0) != (sb < 0) and sb != 0: pts.append(a + (b - a) * (sa / (sa - sb)))
        if len(pts) >= 2 and np.linalg.norm(pts[0] - pts[1]) > 1e-9: segs.append((pts[0], pts[1]))
    return segs


OCCLUDER_CATS = {-2000011, -2000032, -2000035, -2000038}          # walls, floors, roofs, ceilings


def _feature_edges(T, fid=None):
    """edges between triangles of different faces (B-rep edges), boundary edges, and sharp edges"""
    if fid is None and os.environ.get('RVT_NO_RUST_RASTER') != '1':
        try:
            import rvt_fast
            E_ = rvt_fast.feature_edges(np.ascontiguousarray(T, dtype=np.float64), math.cos(FEATURE_ANGLE))      # bit-identical (12-15x)
            if E_ is not None: return E_
        except Exception: pass
    R = np.round(np.asarray(T, float), 6).tolist()
    E = {}
    for i, t in enumerate(R):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ka, kb = tuple(t[a]), tuple(t[b])
            k = (ka, kb) if ka < kb else (kb, ka)
            E.setdefault(k, []).append(i)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(N, axis=1); nl[nl == 0] = 1; N = N / nl[:, None]
    out = []
    cosmax = math.cos(FEATURE_ANGLE)
    for (ka, kb), ts in E.items():
        if len(ts) == 1: out.append((ka, kb)); continue
        if len(ts) == 2:
            i, j = ts
            if fid is not None and fid[i] != fid[j]: out.append((ka, kb)); continue
            if fid is None and abs(float(N[i] @ N[j])) < cosmax: out.append((ka, kb))
    return np.array(out, float).reshape(-1, 2, 3)


def info_cls_topo(self, eid):
    return (self.vis.info.info.get(eid) or {}).get('cls') in ('SiteSurface', 'TopographySurface')


def _silhouette_edges(T):
    """edges shared by two triangles that face opposite ways along the view depth (T: n x 3 x 3 in view coordinates, w = depth)"""
    T = np.asarray(T, float)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])[:, 2]
    R = np.round(T, 5)
    E = {}
    for i in range(len(T)):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ka, kb = tuple(R[i, a]), tuple(R[i, b])
            E.setdefault((ka, kb) if ka < kb else (kb, ka), []).append(i)
    out = [(ka, kb) for (ka, kb), ts in E.items() if len(ts) == 2 and N[ts[0]] * N[ts[1]] < 0]
    return np.array(out, float).reshape(-1, 2, 3)


BELOW_RANGE_CATS = {-2000032, -2000120, -2000919, -2000920, -2000180}     # floors, stairs (runs, landings), ramps


def _clip_polyline_u(P, u0, u1):
    """polyline (n x 2, increasing u) clipped to u0 <= u <= u1 with interpolated end points (a long profile segment has no vertex inside the crop)"""
    out = []
    for a, b in zip(P[:-1], P[1:]):
        lo, hi = max(u0, min(a[0], b[0])), min(u1, max(a[0], b[0]))
        if lo > hi or a[0] == b[0]: continue
        f = lambda u: a + (b - a) * ((u - a[0]) / (b[0] - a[0]))
        pa, pb = (f(lo), f(hi)) if a[0] < b[0] else (f(hi), f(lo))
        if not out or np.linalg.norm(out[-1] - pa) > 1e-9: out.append(pa)
        out.append(pb)
    return np.asarray(out, float) if len(out) >= 2 else np.zeros((0, 2))


_TESS = None


def _tess_fn():
    """Rust tessellator (rvt_fast, bit-identical to rvt_mesh, 13-41x; falls back to the reference inside the adapter), else the reference function"""
    global _TESS
    if _TESS is None:
        try:
            p = os.path.expanduser('~/src/rvt-core/python')
            if os.path.isdir(p) and p not in sys.path: sys.path.append(p)
            import rvt_fast
            _TESS = rvt_fast.tessellate_geometry
        except Exception:
            import rvt_mesh
            _TESS = rvt_mesh.tessellate_geometry
    return _TESS


_FONTS = {}


class _ScaledFont:
    """a substitute font whose advances are scaled to the missing font's (measured mean width ratio on typical Revit label strings)"""
    def __init__(self, f, k): self.f, self.k = f, k
    def getlength(self, t): return self.f.getlength(t) * self.k


# Revit font -> (substitute family, weight, width ratio real / substitute) used only when fontconfig has no real match for the name (host without the Microsoft fonts);
# ratios measured against the real files on host3 (mean over 14 label strings, spread 2-7 %).  Proprietary fonts are installed per user (~/.local/share/fonts), never committed.
_SUBST = {'trebuchet ms': ('Noto Sans', 'regular', 1.068), 'georgia': ('Liberation Serif', 'regular', 1.045), 'arial black': ('DejaVu Sans', 'bold', 1.032),
          'verdana': ('DejaVu Sans', 'regular', 1.013)}


def _font(name, bold):
    if name == 'Arial Narrow' and os.environ.get('RVT_ARIAL_NARROW', 'arial') == 'arial': name = 'Arial'      # see svg.font_stack
    k = (name, bold)
    if k not in _FONTS:
        f = None
        try:
            import subprocess
            from PIL import ImageFont
            out = subprocess.run(['fc-match', '-f', '%{file}|%{family}', '%s:%s' % (name, 'bold' if bold else 'regular')], capture_output=True, text=True, timeout=5).stdout
            path, fam = out.split('|', 1)
            f = ImageFont.truetype(path, 200)
            sub = _SUBST.get(name.lower())
            if sub and name.lower() not in fam.lower() and os.environ.get('RVT_FONT_SUBST', '1') == '1':      # fontconfig fell back to something else: use the measured substitute
                p2 = subprocess.run(['fc-match', '-f', '%{file}', '%s:%s' % (sub[0], sub[1])], capture_output=True, text=True, timeout=5).stdout
                f = _ScaledFont(ImageFont.truetype(p2, 200), sub[2])
        except Exception: f = None
        _FONTS[k] = f
    return _FONTS[k]


def wrap_text(txt, width, em, name, bold=False):
    """word-wrap a text note to its width (model feet; em = rendered font size in model feet); measured with the system font of the same name
    (Liberation Sans is metric-compatible with Arial), 0.5 em per character when no font is found"""
    f = _font(name, bold)
    wd = (lambda t: f.getlength(t) / 200.0 * em) if f else (lambda t: len(t) * 0.5 * em)
    out = []
    for para in txt.split('\n'):
        line = ''
        for w in para.split(' '):
            t = (line + ' ' + w) if line else w
            if line and wd(t) > width: out.append(line); line = w
            else: line = t
        out.append(line)
    return '\n'.join(out)


ANNO_FILTER_CLASSES = ('Section', 'LinearDimString', 'SpotElevation', 'InteriorElev', 'IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol', 'RoomTag', 'SpaceTag', 'AreaTag')


class ViewDrawer:
    def __init__(self, dec, doc, vis=None):
        self.dec = dec; self.doc = doc; self.f = dec.f
        self.vis = vis or Visibility(dec, doc)
        self.stats = collections.Counter()
        from .filters import FilterEval
        self.fe = FilterEval(dec, doc)

    def _rvt22(self):
        c = self.__dict__.get('_r22')
        if c is None:
            from .units import is_2022_plus
            c = self._r22 = bool(is_2022_plus(self.f))        # the framing hidden-line gate is a 2022+ writer behaviour (2020 rst basic draws that geometry in every section)
        return c

    def frame(self, v):
        O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float); Z = np.asarray(v['dir'], float)
        return O, X, Y, Z

    def planes(self, v, O, Z):
        """cut plane depth (w) and far depth in view coordinates; None when absent"""
        kind = v['kind']; crop = v.get('crop') or {}
        if kind == 'plan' and v.get('range'):
            r = v['range']
            wc = r['cut'] - O[2] if Z[2] > 0 else O[2] - r['cut']
            # reflected ceiling plans look up from the cut plane to the view depth (2020 Residential 'attic' RCP: depth unlimited, Revit
            # shows nothing but markers; 'first floor' RCP: cut 7.5, depth 9.0 = the attic level)
            far = r['depth'] if r.get('plan_view_type') == 2 else min(r['depth'], r['bottom'])
            wf = far - O[2] if Z[2] > 0 else O[2] - far
            return wc, wf, Z * (1 if Z[2] > 0 else 1)
        if kind == 'section' and crop.get('basis'):
            B = np.asarray(crop['basis'], float); co = np.asarray(crop['origin'], float); b = crop['bounds']
            near = co + B[2] * b[2][1]; farp = co + B[2] * b[2][0]
            cu = (v.get('cutters') or {}).get('Cutter')
            if cu and cu.get('origin') is not None and os.environ.get('RVT_CUTTER', '1') == '1': near = np.asarray(cu['origin'], float)       # the view's own cut plane
            wc = float((near - O) @ Z)
            wf = float((farp - O) @ Z) if (crop.get('active') or [[1, 1]] * 3)[2][0] else -1e9
            return wc, wf, Z
        return None, -1e9, Z

    def draw(self, vid, *a, **k):
        v = self.doc['views'].get(vid) or self.doc['views'].get(str(vid))
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v) if v else None
        if cr is not None:
            from shapely.geometry import box
            m = 0.05 * max(cr[2] - cr[0], cr[3] - cr[1])
            patterns.CLIP = box(cr[0] - m, cr[1] - m, cr[2] + m, cr[3] + m)
        patterns.WORLD_UV = None
        if v and os.environ.get('RVT_PAT_ORIGIN', '1') == '1' and v.get('kind') in ('plan', 'section'):
            O_, X_, Y_, _ = self.frame(v); patterns.WORLD_UV = (float(-O_ @ X_), float(-O_ @ Y_))       # model patterns are anchored at the world origin, not the view origin
        try: return self._draw(vid, *a, **k)
        finally: patterns.CLIP = None; patterns.WORLD_UV = None

    def _draw(self, vid, px_mm=0.25, max_elems=None, skip_classes=(), skip_cats=()):
        t0 = time.time()
        self._cur_vid = vid
        v = self.doc['views'].get(vid) or self.doc['views'].get(str(vid))
        ev = self.vis.effective(v)
        scale = v.get('scale') or 100
        if v.get('kind') == 'sheet': scale = 1
        O, X, Y, Z = self.frame(v)
        is_rcp = v.get('kind') == 'plan' and (v.get('range') or {}).get('plan_view_type') == 2
        if is_rcp and Z[2] > 0: Z = -Z                                # looking up: depth axis flipped, plan x/y unchanged
        Mv = np.stack([X, Y, Z])                                     # world -> view rows
        wc, wf, _ = self.planes(v, O, Z)
        is_section = v['kind'] == 'section' and v.get('class') == 'DBViewSection'
        cut_w = wc
        ctx = ViewCtx(Z, detail=ev.get('detail_level') or 2, cut_origin=(O + Z * wc) if wc is not None else None, cut_normal=Z if wc is not None else None, kind=v['kind'], scale=scale)
        W = Walker(self.f, ctx)
        from .annot import Annotations
        self.ann = Annotations(self)
        from .annot import Tags
        self.tags = Tags(self)
        from .annot import Markers
        self.markers = Markers(self)
        def _is_anno(e):
            c = self.vis.info.info.get(e, {}).get('cat')
            return CAT_TYPES.get(c) == 'Annotation' or CAT_TYPES.get((self.doc['categories'].get(c) or {}).get('parent')) == 'Annotation'
        W.is_annotation = _is_anno
        W.invisible_gs = {g for g, st in self.doc['gstyles'].items() if st.get('cat') == -2000064 or 'nvisible' in str((self.doc['categories'].get(st.get('cat')) or {}).get('name'))}     # -2000064: invisible lines (unnamed in 2020 Commercial)
        W.is_2d = lambda e: v['kind'] == 'drafting' or _is_anno(e) or self.vis.info.info.get(e, {}).get('cat') == -2002000     # detail items
        res = Resolver(self.doc, ev, scale)
        rcp_under = self.underlay_range(v, O, Z) if is_rcp else None
        elems = self.vis.elements(vid)
        self._vis_elems = set(elems)                 # tags of elements that are not in this view are not drawn (rst basic cross section: CHS / foundation tags)
        prims = []; solids = []      # per element: (eid, cat, tris_uvw, gs)
        occ_owner = []; carve_boxes = {}
        topo = []                    # topography surfaces (meshes, no solids): poche in sections
        occluders = []               # bodies that only hide (internal graphics styles), view coordinates
        datum_ids = []
        stair_skip = set()
        if v['kind'] == 'plan' and not is_rcp:
            for eid in elems:
                if self.vis.info.info[eid]['cls'] != 'StairsElement': continue
                try: sy = self.stairs_symbol(eid, v, O, Mv, scale, res)
                except Exception: sy = None; self.stats['stair_symbol_error'] += 1
                if sy is not None:
                    sp_ = sy[0]
                    bb_ = self.vis.info.bbox(eid)
                    if bb_ is not None and v.get('range') and v['range'].get('cut') is not None and bb_[1][2] < v['range']['cut'] - 0.01 and os.environ.get('RVT_STAIROCC', '1') == '1':
                        try:      # a stair wholly below the cut is hidden by the floors above it (Residential site plan: the basement stair is absent from Revit's DXF)
                            occ_ = self._underlay_occluder(v, O, Mv, elems, bb_[1][2] + 0.5)
                            if occ_ is not None and not occ_.is_empty: sp_ = self._subtract_region(sp_, occ_)
                        except Exception: self.stats['stair_occ_error'] += 1
                    prims += sp_; stair_skip |= sy[1]; self.stats['stair_symbols'] += 1
        for k, eid in enumerate(elems):
            if max_elems and k >= max_elems: break
            if eid in stair_skip: continue
            info = self.vis.info.info[eid]
            if info['cls'] in skip_classes or info['cat'] in skip_cats: continue
            if info['cls'] == 'VolumeOfInterest' and os.environ.get('RVT_SCOPEBOX', '1') == '1': self.stats['scope_box_skipped'] += 1; continue      # scope boxes: not in Revit's element lists (Snowdon East / Parking: FP) nor in its DXF
            if info['cls'] in ('Rebar', 'RebarInSystem', 'AreaReinforcement', 'PathReinforcement') and v['kind'] == 'section' and v.get('view_type') == -1 and os.environ.get('RVT_ELEV_REBAR', '0') != '1': self.stats['rebar_in_elevation_skipped'] += 1; continue      # elevations (view type -1): Revit's DXFs of the Snowdon East / West / North / South carry no rebar, sections and plans do
            if info['cls'] == 'JoistSystem': self.stats['joist_system_skipped'] += 1; continue          # the system's boundary / layout sketch (cyan dashes) is not drawn by Revit (rst basic Level 1, Snowdon L2)
            if ev.get('filters') and info['cls'] in ANNO_FILTER_CLASSES and info['cat'] != INVALID:
                # view filters hide annotation elements too (Snowdon L2: 'Views - Sheets' = NOT Family and Type contains '_Working' hides every section marker)
                fcat = info['cat']
                if info['cls'] == 'Section':      # filters see the marked view's category (Sections / Callouts), not the Viewers category of the marker
                    fcat = -2000537 if (self.f.rec(eid) or {}).get('fields', {}).get('m_sectionCreationMethod') == 202 else -2000200
                elif info['cls'] == 'InteriorElev': fcat = -2000535
                if not self.fe.view_filters(ev, eid, fcat, (self.doc['categories'].get(fcat) or {}).get('parent', INVALID))[0]:
                    self.stats['hidden_by_filter'] += 1; continue
            if v['kind'] == 'plan' and (v.get('discipline') == 2 or os.environ.get('RVT_ABOVECUT_ALL', '1') == '1') and info['cat'] == -2001320 and (v.get('range') or {}).get('cut') is not None:
                # structural plans: framing wholly above the cut plane is not drawn (Snowdon L2: beam 640539 z 13.7..18.3 vs cut 10.1, absent in Revit's sheet)
                bb_ = self.vis.info.bbox(eid)
                if bb_ is not None and bb_[0][2] > v['range']['cut'] + 0.01: self.stats['above_cut_hidden'] += 1; continue
            if info['cls'] in ('Grid', 'Level'): datum_ids.append(eid); continue
            if info['cls'] == 'LinearDimString':
                try: prims += self.ann.dimension(eid, O, Mv, scale, res); self.stats['dimensions'] += 1
                except Exception as ex: self.stats['dimension_error'] += 1
                continue
            if info['cls'] == 'AngularDim':
                try: prims += self.ann.angular_dimension(eid, O, Mv, scale, res); self.stats['angular_dimensions'] += 1
                except Exception: self.stats['dimension_error'] += 1
                continue
            if info['cls'] == 'SpotElevation':
                try:
                    sp = self.ann.spot_slope(eid, O, Mv, scale, res)
                    if sp: self.stats['spot_slopes'] += 1
                    else: sp = self.ann.spot_elevation(eid, O, Mv, scale, res); self.stats['spot_elevations'] += bool(sp)
                    prims += sp
                except Exception: self.stats['spot_error'] += 1
                continue
            if info['cls'] == 'FamilyInstance' and v['kind'] == 'plan' and (ev.get('detail_level') or 2) >= 2:       # family text labels only at medium / fine detail (Residential area plan and attic at coarse detail show none: REF. / DW / W)
                try: prims += self.family_label(eid, O, Mv, scale)
                except Exception as ex_: self.stats['family_label_error'] += 1; self.__dict__.setdefault('_fle', repr(ex_))
            if info['cls'] == 'InteriorElev':
                from .compose import crop_rect_uv as _cru
                cr = _cru(v) if v['kind'] == 'plan' else None
                if cr is not None:
                    pos_ = (self.f.rec(eid, 'InteriorElev') or {}).get('fields', {}).get('m_pos')
                    if pos_ is not None:
                        u_, w_ = ((np.asarray(pos_, float) - O) @ Mv.T)[:2]
                        if not (cr[0] <= u_ <= cr[2] and cr[1] <= w_ <= cr[3]): self.stats['markers_outside_crop'] += 1; continue      # Revit omits elevation markers outside the crop (Commercial Mezzanine)
                try: prims += _hang(self.markers.elevation(eid, O, Mv, scale, res)); self.stats['elevation_markers'] += 1
                except Exception as ex: self.stats['marker_error'] += 1
                continue
            if info['cls'] == 'InteriorElevArrow': continue
            if info['cls'] == 'StairsPathElement':
                try: stl = self.f.eid(self.f.rec(eid, 'StairsPathElement')['fields']['m_stairsLinkElementId']['m_linkInstOrHostId'])
                except Exception: stl = None
                if stl is not None and stl not in elems: self.stats['stair_paths_hidden'] += 1; continue          # the stair itself is not shown in this view (rst basic Level 2): no path
                try: prims += self.stairs_path(eid, v, O, Mv, scale, res, info['cat']); self.stats['stair_paths'] += 1
                except Exception: self.stats['stair_path_error'] += 1
                continue
            if info['cls'] == 'StairsPathElement':
                try: prims += self.stairs_path_text(eid, O, Mv, scale, v)
                except Exception: self.stats['stairs_path_error'] += 1
                continue
            if info['cls'] == 'PropertyLineSegment':
                try: prims += self.property_line(eid, O, Mv, res, v)
                except Exception: self.stats['property_line_error'] += 1
                continue
            if info['cls'] == 'ColorFillLegend':
                try: prims += self.color_legend(eid, v, O, Mv, scale); self.stats['legends'] += 1
                except Exception: self.stats['legend_error'] += 1
                continue
            if info['cls'] == 'Section':
                if (self.f.rec(eid) or {}).get('fields', {}).get('m_sectionCreationMethod') == 202:
                    from .annot import callout
                    try: prims += _hang(callout(self, eid, O, Mv, scale, res, vid)); self.stats['callouts'] += 1
                    except Exception: self.stats['marker_error'] += 1
                elif v.get('kind') == 'section':
                    from .annot import section_marker, section_head_extent
                    try:
                        sp_ = self.vis.section_plane_line(eid, v)
                        if sp_:
                            pts_ = sp_[0]
                            from .datums import Datums
                            from .compose import crop_rect_uv as _cru2
                            ar_ = _cru2(v)                              # cut at the crop region (Residential East elevation: the A-2 head sits at the crop top), inset like plan markers
                            if ar_ is not None:
                                i_ = 0.2375 / 12 * scale; top_ = i_
                                he_ = section_head_extent(self, eid) if os.environ.get('RVT_HEADFIT', '1') == '1' else None
                                if he_: top_ = he_ * scale          # the head symbol (circle + stub, 0.0503 ft of paper outward) sits entirely inside the crop: line cut one symbol length below the crop top (Residential East: Revit symbol tip at the crop top)
                                if he_ and ((np.asarray(pts_[0], float) - O) @ Mv.T)[1] <= ar_[3] + 1e-6: top_ = -1e6     # the line's own top lies inside the crop: the head hangs outside it unclamped (rst basic: line ends at the plane top)
                                ar_ = (ar_[0] + i_, ar_[1] + i_, ar_[2] - i_, ar_[3] - top_)
                            if ar_ is not None:                       # the marker line is cut at the annotation crop region (rst basic longitudinal section: S202 line ended 400 px below the view)
                                P_ = np.asarray([((np.asarray(q, float) - O) @ Mv.T)[:2] for q in pts_]); vis_ = []
                                for a_, b_ in zip(P_[:-1], P_[1:]):
                                    sg_ = Datums._clip(a_, b_, ar_)
                                    if sg_ is not None: vis_.append(sg_)
                                if not vis_: continue
                                Q_ = [vis_[0][0]]
                                for a_, b_ in vis_:
                                    if np.linalg.norm(a_ - Q_[-1]) > 1e-6: Q_.append(a_)
                                    Q_.append(b_)
                                pts_ = [np.asarray(O) + np.asarray(Mv.T @ np.array([q[0], q[1], 0.0])) for q in Q_]
                            prims += _hang(section_marker(self, eid, O, Mv, scale, res, vid, pts=pts_)); self.stats['section_markers'] += 1
                    except Exception: self.stats['marker_error'] += 1
                elif v.get('kind') == 'plan':
                    from .annot import section_marker
                    try: prims += _hang(section_marker(self, eid, O, Mv, scale, res, vid)); self.stats['section_markers'] += 1
                    except Exception: self.stats['marker_error'] += 1
                continue
            if info['cls'] in ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol', 'RoomTag', 'SpaceTag', 'AreaTag'):
                try: prims += self.tags.tag(eid, O, Mv, scale, res); self.stats['tags'] += 1
                except Exception as ex: self.stats['tag_error'] += 1
                continue
            if info['cls'] == 'ContourLabelingElem':
                try:
                    from .compose import crop_rect_uv as _cru3
                    prims += self.ann.contour_labels(eid, O, Mv, scale, res, _cru3(v))
                except Exception: self.stats['contour_label_error'] += 1
                continue
            if info['owner'] == vid and info['cls'] == 'TextNote':
                tp = self.text_note(eid, O, Mv, scale)
                if tp:
                    prims.append(tp); self.stats['text_notes'] += 1
                    try: prims += self.text_note_leaders(eid, O, Mv, scale, res, info['cat'])
                    except Exception: self.stats['leader_error'] += 1
                continue
            if info['cls'] == 'RoomElem' and v['kind'] == 'plan':
                try: prims += self.room_fill(eid, v, O, Mv, wc)
                except Exception: self.stats['room_fill_error'] += 1
            if info['cls'] == 'CurveElem' and info['cat'] == -2000077:
                try:
                    ip = self.insulation(eid, O, Mv, res)
                    if ip is not None: prims += ip; self.stats['insulation'] += 1; continue
                except Exception: self.stats['insulation_error'] += 1
            if info['cls'] in NO_SOLID_CLASSES: self.stats['spatial_skipped'] += 1; continue     # rooms/spaces/areas: drawn through their sub-categories (interior fill, reference), stage 5
            try: pieces = W.walk_record(eid)
            except Exception as ex:
                self.stats['walk_error'] += 1
                if os.environ.get('RVT_DEBUG'): import traceback; traceback.print_exc()
                continue
            cid = info['cat']
            fvis, fovs = self.fe.view_filters(ev, eid, cid, (self.doc['categories'].get(cid) or {}).get('parent', INVALID)) if ev.get('filters') else (True, [])
            if not fvis: self.stats['hidden_by_filter'] += 1; continue
            st_ = elems.get(eid) if isinstance(elems, dict) else None
            pov = None
            if st_ in PHASE_IDX and self.vis.pfilters.get(ev.get('phase_filter')):
                if self.vis.pfilters[ev['phase_filter']]['presentation'][PHASE_IDX[st_]] == 2:
                    pov = self.doc.get('phase_overrides', {}).get(PHASE_IDX[st_])
            ov = res.overrides(eid, cid, fovs, pov)
            if info['cls'] in ('SiteSurface', 'TopographySurface'): topo.append((eid, cid, ov))
            anno = CAT_TYPES.get(cid) == 'Annotation' or CAT_TYPES.get((self.doc['categories'].get(cid) or {}).get('parent')) == 'Annotation'
            if anno and info['cls'] == 'FamilyInstance':
                try: prims += self.tags.instance_labels(eid, O, Mv)
                except Exception: self.stats['label_error'] += 1
                try:                                                      # leaders of generic annotations / keynote notes: anchor -> elbow -> end (Residential details 4 and 5 of sheet A-2)
                    for lo_ in (self.f.rec(eid)['fields'].get('m_leaders') or []):
                        l_ = ob(lo_); pts_ = [((np.asarray(l_[k_], float) - O) @ Mv.T)[:2] for k_ in ('m_anchor', 'm_elbow', 'm_end') if l_.get(k_)]
                        if len(pts_) == 3:
                            prims.append({'t': 'line', 'pts': [q_.tolist() for q_ in pts_], 'style': res.line(None, cid, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation', 'part': 'leader'})
                            self.stats['annotation_leaders'] += 1
                except Exception: self.stats['leader_error'] += 1
            for tx_ in pieces['texts']:
                q = dict(tx_); q['origin'] = ((np.asarray(q['origin'], float) - O) @ Mv.T)[:2].tolist(); q['layer'] = 'text'
                if q.get('x') is not None:                       # instance transform carries the annotation scale: direction in view coordinates, size x scale (Help Button '?')
                    xv = (Mv @ np.asarray(q['x'], float))[:2]; k_ = float(np.linalg.norm(xv))
                    if k_ > 1e-9:
                        q['x'] = (xv / k_).tolist()
                        if q.get('y') is not None: q['y'] = ((Mv @ np.asarray(q['y'], float))[:2] / k_).tolist()
                        if abs(k_ - 1.0) > 1e-6:
                            q['size'] = (q.get('size') or 0.0078) * k_
                            for kk_ in ('box', 'text_box', 'text_off'):
                                if q.get(kk_): q[kk_] = [a_ * k_ for a_ in q[kk_]]
                prims.append(q)
            under_occ = None
            if v['kind'] == 'plan' and v.get('range') and info['owner'] == INVALID and not is_rcp:
                rg = v['range']; zlo_ = min(x for x in (rg.get('depth'), rg.get('bottom')) if x is not None); bb_ = self.vis.info.bbox(eid)
                if bb_ is not None and rg.get('top') is not None and bb_[1][2] < zlo_ - 1e-6 and not anno:
                    under_occ = self._underlay_occluder(v, O, Mv, elems, bb_[1][2])
                elif (bb_ is not None and rg.get('top') is not None and not anno and cid == -2001320 and v.get('discipline') != 2 and rg.get('cut') is not None
                      and bb_[1][2] < rg['cut'] - 0.01 and os.environ.get('RVT_FRAME_OCC', '1') == '1'):
                    under_occ = self._underlay_occluder(v, O, Mv, elems, bb_[1][2])      # framing under a floor in a non-structural plan: the floor hides its symbolic lines (Snowdon L4 / L5: Revit's DXF has none)
            curves_ = pieces['curves']
            if info['cls'] in ('Rebar', 'RebarInSystem'):
                try: curves_ = self.rebar_bars(eid, curves_) or curves_
                except Exception: self.stats['rebar_error'] += 1
            plant_c = None
            if cid == -2001360 and info['cls'] == 'FamilyInstance' and v['kind'] == 'plan' and os.environ.get('RVT_PLANT', '1') == '1':
                try:
                    allp_ = np.concatenate([np.asarray(c_['pts'], float)[:, :2] for c_ in curves_ if c_.get('pts') is not None and len(c_['pts'])])
                    plant_c = ((allp_.min(0) + allp_.max(0)) / 2, float(max(allp_.max(0) - allp_.min(0))) / 2)      # planting symbol centre / radius (world)
                except Exception: plant_c = None
            for c in curves_:
                if 'pts' not in c: continue                  # image placements etc. (drawn by the sheet / title block code)
                if not self.drawable_gs(c.get('gs')): continue
                if self._gs_hidden(ev, c.get('gs')): self.stats['hidden_subcategory_lines'] += 1; continue
                if v['kind'] == 'plan' and self._elevation_swing(c.get('gs')): self.stats['elevation_swing_skipped'] += 1; continue      # door/window 'Elevation Swing' lines show only in elevations/sections (Residential plan 32: Revit DXF has none)
                if info['cls'] in ('SiteSurface', 'TopographySurface') and v['kind'] in ('section', '3d'): continue   # contour/surface curves are not drawn in elevations (the ground profile comes from the mesh)
                pts = (np.asarray(c['pts'], float) - O) @ Mv.T
                if plant_c is not None and len(c['pts']) == 2:
                    a_, b_ = np.asarray(c['pts'], float)[:, :2]; ab_ = b_ - a_; L_ = float(np.linalg.norm(ab_))
                    if L_ > 0.5 * plant_c[1]:
                        t_ = float((plant_c[0] - a_) @ ab_) / (L_ * L_)
                        if 0.15 < t_ < 0.85 and float(np.linalg.norm(a_ + ab_ * t_ - plant_c[0])) < 0.05 * plant_c[1] + 0.02:
                            self.stats['planting_diameter_skipped'] += 1; continue      # the symbol's straight lines through its centre (Revit draws the circle and the spokes from the centre, not the diameters)
                if is_section and v['kind'] == 'section' and wf is not None and wf > -1e8 and pts[:, 2].max() < wf - 1e-6: self.stats['curves_beyond_far_clip'] += 1; continue
                if is_section and v['kind'] == 'section' and cut_w is not None and pts[:, 2].min() > cut_w + 1e-6: self.stats['curves_before_cut'] += 1; continue      # symbol lines wholly in front of the section plane (planting 18 ft before the building section)      # family symbol lines (planting) behind the far clip are not drawn
                if cut_w is not None and not is_section and (pts[:, 2] > cut_w + 1e-6).all() and False: continue
                lay = 'symbolic'
                if v['kind'] == 'plan' and not anno and info['cls'] == 'FamilyInstance' and cid not in (-2001330, -2001320, -2001300) and cut_w is not None and (c.get('flags') or 0) & 0x80000 and not (c.get('flags') or 0) & 0x2a0 and (pts[:, 2] > cut_w + 1e-6).all():
                    self.stats['family_lines_above_cut'] += 1; continue      # family curves flagged 0x80000 (not 0x20/0x80/0x200) lying above the cut plane (door head / overhead track lines) are not in Revit's plan (Residential 32/36/basement: P +1.4..6 pts, R -0.3..1)
                if is_rcp and not anno and cut_w is not None and (pts[:, 2] > cut_w + 1e-6).all():
                    # family plan symbols below a ceiling plan's cut (furniture, fixtures): only in the underlay, halftone
                    if rcp_under is None: continue
                    zc = -pts[:, 2]
                    if zc.max() < rcp_under[0] - 1e-6 or zc.min() > rcp_under[1] + 1e-6: continue
                    lay = 'underlay'
                st = res.line(c.get('gs'), cid, 'proj', eid, ov=dict(ov, halftone=True) if lay == 'underlay' else ov, annotation=anno)
                if under_occ is not None and len(pts) > 1:
                    # plan symbols of elements in the underlay range are hidden by floors/roofs/ceilings between them and the view (looking down)
                    from shapely.geometry import LineString
                    try: diff = LineString(pts[:, :2]).difference(under_occ)
                    except Exception: diff = LineString(pts[:, :2])
                    if diff.is_empty: self.stats['underlay_occluded_lines'] += 1; continue
                    for part in getattr(diff, 'geoms', [diff]):
                        if part.geom_type == 'LineString' and len(part.coords) > 1:
                            prims.append({'t': 'line', 'pts': [list(q) for q in part.coords], 'style': st, 'elem': eid, 'layer': lay})
                    continue
                if os.environ.get('RVT_FRAMEGATE', '1') == '1' and self._rvt22() and (v['kind'] == 'section' or (v['kind'] == 'plan' and v.get('discipline') != 2)) and cid == -2001320 and (c.get('flags') or 0) in (0x1088004, 0x1088204, 0x10880e0) and ((v.get('display') or {}).get('m_model') or {}).get('m_showHiddenLinesVal') != 2:
                    self.stats['framing_hidden_style_skipped'] += 1; continue      # the family's hidden-line geometry (S-BEAM-HDLN in Revit's DXF) is only drawn when the view shows hidden lines (m_showHiddenLinesVal 2: Snowdon Longitudinal); Cross Section P .837 -> .958
                if v['kind'] == 'plan' and cid == -2000151 and info['cls'] == 'FamilyInstance' and ((c.get('flags') or 0) & 0x1088000) == 0x1088000 and not (c.get('flags') or 0) & 0x8000000 and ((v.get('display') or {}).get('m_model') or {}).get('m_showHiddenLinesVal') != 2: continue      # generic-model families' hidden-line geometry in plans (Snowdon L4 precision .974 -> .998, L2 .959 -> .971, recall -0.2..-0.7)
                pr = {'t': 'line', 'pts': pts[:, :2].tolist(), 'style': st, 'elem': eid, 'layer': lay}
                if is_section and not anno and len(pts) > 1 and cid not in UNOBSCURED_CATS:
                    pr['_w'] = pts             # depth-tested below (elevations/sections)
                    if cid in (-2000023, -2000014): pr['_eps'] = 1.5      # doors/windows sit recessed inside the wall thickness
                prims.append(pr)
            for fl in pieces['fills']:
                loops = [((np.asarray(l, float) - O) @ Mv.T)[:, :2].tolist() for l in fl.get('loops') or [] if l]
                if not loops: continue
                pid = fl.get('pattern'); pat = self.doc['fill_patterns'].get(pid) if pid not in (None, -1) else None
                col = fl.get('color')
                if isinstance(col, int) and col >= 1 << 24: col = [0, 0, 0]          # 0x1000000: no explicit colour (black)
                if pat is not None and not pat.get('solid'):
                    reg = patterns.region(loops)
                    if reg is None: continue
                    rot = 0.0
                    pl = fl.get('placer') or {}
                    if pl.get('m_dir') and fl.get('R'):
                        dv = Mv @ (np.asarray(fl['R'], float) @ np.array([pl['m_dir'][0], pl['m_dir'][1], 0.0]))
                        if np.hypot(dv[0], dv[1]) > 1e-9: rot = math.atan2(dv[1], dv[0])
                    prims.append({'t': 'segs', 'segs': patterns.hatch(reg, pat, scale, view_rot=rot), 'style': {'w': 0.1, 'rgb': col if isinstance(col, list) else [0, 0, 0], 'dash': None},
                                  'elem': eid, 'layer': 'symbolic_fill'})
                elif 'placer' in fl and fl.get('edge_gs') not in (None, -1) and fl['edge_gs'] not in W.invisible_gs and self._region_rgb(fl['edge_gs'], res) not in (None, [255, 255, 255]):
                    # filled region type with a visible line style: its colour is the style's (Commercial 'Help Button' Solid Blue / Solid Black regions)
                    prims.append({'t': 'fill', 'loops': loops, 'color': self._region_rgb(fl['edge_gs'], res), 'pattern': pid, 'gs': fl['edge_gs'], 'elem': eid, 'layer': 'symbolic_fill'})
                elif 'placer' in fl:
                    # solid / pattern-less fill inside a detail or annotation family: a masking region (white) that hides what is drawn
                    # before it in the view's draw order (2020 Residential 'at grade' vs Revit's DXF: lines cut where components overlap)
                    prims.append({'t': 'fill', 'loops': loops, 'color': [255, 255, 255], 'elem': eid, 'layer': 'mask'})
                else:
                    prims.append({'t': 'fill', 'loops': loops, 'color': col if 'placer' in fl else fl.get('color'), 'pattern': pid, 'elem': eid, 'layer': 'symbolic_fill'})
            for s in pieces['solids']:
                if self._gs_hidden(ev, s.get('gs')): self.stats['hidden_subcategory_solids'] += 1; continue
                if not self.drawable_gs(s.get('gs')):
                    # internal-category bodies (2020 Residential wall bodies, cat -2000896): their edges are not drawn but they hide
                    # what lies behind them (elevations otherwise show every interior object through the walls)
                    self.stats['hidden_internal_solids'] += 1
                    if cid in OCCLUDER_CATS:
                        T = self._tess(s)
                        if T is not None and len(T[0]): occluders.append((T[0] - O) @ Mv.T); occ_owner.append(eid)
                    continue
                T = self._tess(s)
                if T is None or not len(T[0]): continue
                tris, fid = T[0], T[1]
                uvw = (tris - O) @ Mv.T
                if s.get('cutnode') and cut_w is not None and v['kind'] == 'plan' and os.environ.get('RVT_CUTNODE', '1') == '1':
                    z0_, z1_ = float(uvw[:, :, 2].min()), float(uvw[:, :, 2].max())
                    if not (z0_ <= cut_w <= z1_): uvw[:, :, 2] += cut_w - (z0_ + z1_) / 2      # the family's cut-profile extrusion follows the cut plane (Snowdon steel columns in L4: base-level slab moved to the cut)
                m = self.solid_material(T[2] if len(T) > 2 else None)
                ov2 = dict(ov, _mat=m) if m is not None else ov
                if (v['kind'] in ('section', '3d') or (v['kind'] == 'plan' and cid == -2000032 and not is_rcp)) and len(T) > 2 and T[2] is not None: ov2 = dict(ov2, _frs=T[2])   # plans: floor top surface pattern (Commercial 'Sand' dots under the room colours)
                solids.append((eid, cid, uvw, fid, s.get('gs'), ov2))
        if datum_ids:
            from .datums import Datums
            from .sheet import SheetComposer
            imp = SheetComposer.imperial(type('X', (), {'doc': self.doc, 'IMPERIAL': SheetComposer.IMPERIAL})())
            try: prims += Datums(self).draw(vid, v, datum_ids, O, Mv, scale, res, imp)
            except Exception as ex: self.stats['datum_error'] += 1; print('datum error', repr(ex))
        self.stats['solids'] += len(solids)
        if not solids and not prims: return {'prims': self._finish(prims, O, Mv), 'stats': dict(self.stats)}
        # depth range clip
        allp = []
        clipped = []
        # underlay (plan views with an underlay level): bodies wholly below the view depth that reach into the underlay range are drawn
        # halftone in projection, hidden only by each other (Revit draws the underlay below the model: the level 2 floor does not hide it)
        under = []
        uw = self.underlay_range(v, O, Z) if v['kind'] == 'plan' else None
        lim = (uw[2] * wc if is_rcp else wf) if uw is not None and wc is not None else None     # main range starts at: plan bottom / RCP cut
        if lim is not None and lim > -1e8:
            rest = []
            for sol in solids:
                z = sol[2][:, :, 2] * uw[2]                           # heights above the view origin
                if z.max() < lim - 1e-3 and z.max() >= uw[0] - 1e-6 and z.min() <= uw[1] + 1e-6:
                    T = sol[2].copy(); T[:, :, 2] = z; under.append((sol[0], sol[1], T) + tuple(sol[3:]))
                else: rest.append(sol)
            solids = rest
            if under: prims += self.underlay(under, uw, px_mm, scale, res)
        if v['kind'] == 'section' and elems:
            try:
                carve_boxes = self._opening_boxes(elems, O, Mv)
                if carve_boxes:
                    occluders = [self._carve_tris(T_, carve_boxes[o_]) if o_ in carve_boxes else T_ for T_, o_ in zip(occluders, occ_owner)]
                    self.stats['carved_hosts'] += len(carve_boxes)
            except Exception: self.stats['carve_error'] += 1
        for eid, cid, uvw, fid, gs, ov in solids:
            T = uvw
            idx = np.arange(len(T))
            if cut_w is not None:
                keep_full = (T[:, :, 2] <= cut_w + 1e-9).all(1)
                T2 = _clip_tris_halfspace(T, np.array([0, 0, 1.0]), cut_w)
            else: T2 = T
            if wf is not None and wf > -1e8:
                # plans: floors, stairs and ramps stay visible down to 4 ft below the bottom of the view range (Revit's view range
                # exception; writer test file Plan L2 shows the level 2 floor whose top lies on the view's bottom)
                if not (v['kind'] == 'plan' and not is_rcp and cid in BELOW_RANGE_CATS and T[:, :, 2].max() >= wf - 4.0):
                    T2 = _clip_tris_halfspace(T2, np.array([0, 0, -1.0]), -wf)
            if len(T2): clipped.append((eid, cid, T2, uvw, fid, gs, ov)); allp.append(T2.reshape(-1, 3))
        if not allp:
            for p in prims: p.pop('_w', None)
            return {'prims': self._finish(prims, O, Mv), 'stats': dict(self.stats)}
        P = np.concatenate(allp)
        px = px_mm / 304.8 * scale                                    # pixel size in model feet
        bx = [P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max()]
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v)
        if cr is not None:      # only the crop region is shown: a whole topography surface in a 1:8 detail made a 64 Mpx coarse buffer (357 s)
            mg = 0.05 * max(cr[2] - cr[0], cr[3] - cr[1]) + 2 * px
            bx = [max(bx[0], cr[0] - mg), max(bx[1], cr[1] - mg), min(bx[2], cr[2] + mg), min(bx[3], cr[3] + mg)]
            if bx[0] >= bx[2] or bx[1] >= bx[3]: bx = [P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max()]
        db = DepthBuffer(bx[0], bx[1], bx[2], bx[3], px)
        for c in clipped:
            if c[1] == -2003500 and v['kind'] == 'section': continue        # stacked-wall parents duplicate their child walls (and cover curtain-wall storefronts): not occluders (Commercial east/south elevation DXF R 0.66/0.69 -> 0.80/0.85)
            db.add(self._carve_tris(c[2], carve_boxes[c[0]]) if c[0] in carve_boxes else c[2])
        for T in occluders:
            if cut_w is not None: T = _clip_tris_halfspace(T, np.array([0, 0, 1.0]), cut_w)
            if wf is not None and wf > -1e8: T = _clip_tris_halfspace(T, np.array([0, 0, -1.0]), -wf)
            if len(T): db.add(T)
        caps = []
        # cut regions
        if cut_w is not None:
            for eid, cid, T2, uvw, fid, gs, ov in clipped:
                if cid == -2003500 and v['kind'] in ('section', 'plan') and os.environ.get('RVT_STACKCUT', '0') == '0': continue      # stacked-wall parents duplicate their child walls: their cut outlines are not drawn (Commercial Typ. Parapet precision .688 -> .966, Typ. Wall at Grade .621 -> .804; plans: Level 1 .933 -> .988, plan 36 .757 -> .953, Mezzanine .943 -> .984)
                segs = _plane_section(uvw, np.array([0, 0, 1.0]), cut_w)
                if not segs: continue
                st = res.line(gs, cid, 'cut', eid, ov=ov)
                loops = self._loops(segs)
                loops2 = [[p[:2] for p in l] for l in loops]
                for l in loops2:
                    # a cut of a solid is closed: an open chain whose ends are close relative to its length lost a face of the mesh (2020
                    # Residential eave detail: wall 206435 without its bottom face) -> close it with a straight edge
                    if len(l) > 3 and not np.allclose(l[0], l[-1], atol=1e-6):
                        Lp = np.asarray(l, float)[:, :2]; per = float(np.linalg.norm(np.diff(Lp, axis=0), axis=1).sum())
                        if np.linalg.norm(Lp[0] - Lp[-1]) < 0.2 * per: l.append(list(l[0]))
                closed2 = [l for l in loops2 if len(l) > 3 and np.allclose(l[0], l[-1], atol=1e-6)]
                if closed2:                     # open fragments next to closed loops come from faces touching the plane: drop them
                    loops2 = closed2
                    segs = [(np.array(a), np.array(b)) for l in loops2 for a, b in zip(l, l[1:])]
                if closed2 and cid == -2000011 and eid in carve_boxes and cut_w is not None:
                    # hosted door / window openings are missing in the saved wall solid: take their box out of the cut region where the section plane crosses it
                    try:
                        from shapely.geometry import box as sbox
                        from shapely.ops import unary_union
                        rects = [sbox(lo[0], lo[1], hi[0], hi[1]) for lo, hi in carve_boxes[eid] if lo[2] - 1e-6 <= cut_w <= hi[2] + 1e-6]
                        reg0 = patterns.region(closed2) if rects else None
                        if reg0 is not None:
                            reg1 = reg0.difference(unary_union(rects))
                            if not reg1.equals(reg0):
                                nl = []
                                for pg in getattr(reg1, 'geoms', [reg1]):
                                    if pg.geom_type != 'Polygon' or pg.area < 1e-9: continue
                                    nl.append([list(q) for q in pg.exterior.coords]); nl += [[list(q) for q in r_.coords] for r_ in pg.interiors]
                                if nl:
                                    closed2 = loops2 = nl
                                    segs = [(np.array(a), np.array(b)) for l in loops2 for a, b in zip(l, l[1:])]
                                    self.stats['cut_openings'] += 1
                    except Exception: self.stats['carve_error'] += 1
                caps.append(loops2)
                prim = {'t': 'cut', 'loops': loops2, 'segs': [[a[:2].tolist(), b[:2].tolist()] for a, b in segs], 'style': st, 'elem': eid, 'cat': cid, 'layer': 'cut'}
                fill = self.cut_fill(eid, cid, gs, ov, ev.get('detail_level') or 2)
                if fill and ov.get('halftone'):
                    from .style import HALFTONE_MIX
                    fill = dict(fill, color=[int(round(a + (255 - a) * HALFTONE_MIX)) for a in fill['color']])
                if fill:
                    reg = patterns.region([l for l in loops2 if len(l) > 3 and np.allclose(l[0], l[-1], atol=1e-6)])
                    pat = self.doc['fill_patterns'].get(fill['pattern'])
                    if reg is not None and pat:
                        if pat.get('solid'): prim['fill'] = fill['color']
                        else: prims.append({'t': 'segs', 'segs': patterns.hatch(reg, pat, scale), 'style': {'w': 0.1, 'rgb': fill['color'], 'dash': None}, 'elem': eid, 'layer': 'cut_fill'})
                if cid in (-2000011, -2000032, -2000035) and closed2 and (ev.get('detail_level') or 2) != 1 and (ov.get('cut_fg_visible') is not False or os.environ.get('RVT_CUTSURF', '1') == '1'):
                    try: self.wall_layers(eid, closed2, Mv, scale, res, ov, prims, st, cid)
                    except Exception: self.stats['layer_error'] += 1
                prims.append(prim)
                self.stats['cut_elements'] += 1
        if topo and v['kind'] == 'plan' and not is_rcp and os.environ.get('RVT_TOPO_OUTLINE', '1') == '1':
            for eid, cid, ov in topo:
                try: self.topo_boundary(eid, cid, ov, O, Mv, res, prims)
                except Exception: self.stats['topo_boundary_error'] += 1
        if cut_w is not None and topo and v["kind"] == "section":
            for eid, cid, ov in topo:
                try:
                    from .compose import crop_rect_uv
                    caps += self.topo_poche(eid, cid, ov, O, Mv, cut_w, scale, res, prims, crop_rect_uv(v))
                except Exception: self.stats['topo_error'] += 1
                if os.environ.get('RVT_TOPO_SIL', '1') == '1':
                    try:                                                      # the ground beyond the plane: its silhouette edges with hidden-line removal (Residential west elevation: Revit draws several ground lines, ours only the profile)
                        import rvt_elemmesh as E_
                        T_ = np.asarray(E_.element_mesh(self.f.g, eid).get('tris') or [], float).reshape(-1, 3, 3)
                        if len(T_):
                            T_ = _clip_tris_halfspace((T_ - O) @ Mv.T, np.array([0, 0, 1.0]), cut_w)
                            if len(T_):
                                Es_ = _silhouette_edges(T_)
                                vis_ = [(a, b) for a, b in db.visible_parts(Es_, px * 2.0) if np.hypot(*(b[:2] - a[:2])) > px * 0.5] if len(Es_) else []
                                if vis_: prims.append({'t': 'segs', 'segs': [[a[:2].tolist(), b[:2].tolist()] for a, b in vis_], 'style': res.line(None, cid, 'proj', eid, ov=ov), 'elem': eid, 'layer': 'projection'})
                    except Exception: self.stats['topo_silhouette_error'] += 1
        prims = self.merge_cut_outlines(prims)
        # cut caps (the cut faces at the cut plane) hide what lies below them
        for loops2 in caps:
            reg = patterns.region([l for l in loops2 if len(l) > 3 and np.allclose(l[0], l[-1], atol=1e-6)])
            if reg is None: continue
            try:
                import mapbox_earcut as earcut
                for poly in getattr(reg, 'geoms', [reg]):
                    rings = [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors]
                    verts = np.array([q for r in rings for q in r], float)
                    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
                    idx = earcut.triangulate_float64(verts, ends).reshape(-1, 3)
                    T = np.zeros((len(idx), 3, 3)); T[:, :, :2] = verts[idx]; T[:, :, 2] = cut_w
                    db.add(T)
            except Exception as ex: self.stats['cap_error'] += 1
        # projected edges with hidden-line removal
        eps = px * 2.0
        for eid, cid, T2, uvw, fid, gs, ov in clipped:
            E = _feature_edges(T2, None)
            if cut_w is not None: E = E[~((np.abs(E[:, 0, 2] - cut_w) < 1e-6) & (np.abs(E[:, 1, 2] - cut_w) < 1e-6))]       # edges ON the cut plane belong to the cut outline
            if cid in UNOBSCURED_CATS or (cid == -2001300 and v['kind'] == 'plan' and (v.get('range') or {}).get('bottom') is not None and (self.vis.info.bbox(eid) is not None) and self.vis.info.bbox(eid)[1][2] >= v['range']['bottom'] - 1e-6 and self.vis.info.bbox(eid)[1][2] >= (v['range'].get('cut') or 0) - 12.0):                 # rebar: drawn through its host (Revit 'view unobscured' in the sample views); foundation slabs inside a plan's primary range show through the slab above them (Snowdon Parking pile caps / strip footings)
                vis = [(a, b) for a, b in E if np.hypot(*(b[:2] - a[:2])) > px * 0.5]
            else: vis = [(a, b) for a, b in db.visible_parts(E, eps) if np.hypot(*(b[:2] - a[:2])) > px * 0.5]      # end-on edges collapse to points
            if not vis: continue
            st = res.line(gs, cid, 'proj', eid, ov=ov)
            prims.append({'t': 'segs', 'segs': [[a[:2].tolist(), b[:2].tolist()] for a, b in vis], 'style': st, 'elem': eid, 'layer': 'projection'})
        # surface patterns of the visible faces (brick, shingles, block...): face material -> Material.surface_pattern, hatched on the
        # projected front-facing triangles, kept where the depth test says the face is visible (sample points of the hatch lines)
        if v['kind'] in ('section', '3d', 'plan') and scale <= 200:
            try:
                for eid, cid, T2, uvw, fid, gs, ov in clipped:
                    if ov.get('_frs') is not None: self.surface_hatch(eid, cid, uvw, ov['_frs'], db, eps, scale, prims, ov)
            except Exception: self.stats['surface_error'] += 1
        dord = v.get('draw_order') or []
        unlisted = -1
        if not dord:
            # no draw order stored (every 2020 Commercial view): view-specific elements still paint over the model in creation (id) order,
            # so their masking regions hide model lines (parapet detail: wall/insulation below the break line); other elements stay model
            owned = sorted({p.get('elem') for p in prims if p.get('elem') is not None and self.vis.info.info.get(p.get('elem'), {}).get('owner') == vid})
            if any(p.get('layer') == 'mask' and p.get('elem') in set(owned) for p in prims): dord = owned; unlisted = -2
        if dord:
            rank = {e: i for i, e in enumerate(dord)}; top = len(dord)
            for p in prims:
                if p.get('layer') in ('cut', 'cut_fill', 'projection'): continue        # model content stays below detail items
                p['order'] = rank.get(p.get('elem'), top if p.get('layer') in ('text', 'annotation', 'annotation_fill', 'datum') else unlisted)
        # family symbolic lines in sections/elevations (door swings, window and furniture elevation symbols) are hidden by what is in
        # front of them like model edges (2020 Residential elevations showed every interior door through the walls); tolerance 3"
        eps_s = max(eps, 0.25)
        out = []
        for p in prims:
            P = p.pop('_w', None)
            if P is None: out.append(p); continue
            E = np.stack([P[:-1], P[1:]], 1)
            vis = [(a, b) for a, b in db.visible_parts(E, max(eps_s, p.pop('_eps', 0.0))) if np.hypot(*(b[:2] - a[:2])) > px * 0.5]
            if vis: out.append(dict(p, t='segs', segs=[[a[:2].tolist(), b[:2].tolist()] for a, b in vis], pts=None))
        prims = out
        for k_, v_ in gfx.UNKNOWN_CLASSES.items(): self.stats['unknown_gnode ' + k_] = v_
        self.stats['seconds'] = round(time.time() - t0, 1)
        return {'prims': self._finish(prims, O, Mv), 'stats': dict(self.stats), 'conds_unknown': {str(k): v for k, v in W.unknown_conds.items()}}

    def insulation(self, eid, O, Mv, res):
        """batt insulation (CurveElem, 'Insulation Batting Lines', m_data.m_oUserData: m_width W, m_scale = bulge ratio): Revit's export
        (2020 Residential 'typ. wall' DXF splines) = one chain of cubic S-curves zigzagging between the lines +-W/(2 ratio), step q = W/4 along
        the curve, joined on each side by half loops spanning 2q that reach +-W/2. Straight curves only (None otherwise)."""
        fl = self.f.rec(eid)['fields']
        ud = ((fl.get('m_data') or {}).get('m_oUserData') or {}).get('obj') or {}
        W = ud.get('m_width'); ratio = ud.get('m_scale') or 2.0
        c = ((fl.get('m_pCurveDriver') or {}).get('obj') or {}).get('m_pCrv') or {}
        if not W or self.f.tagname(c.get('ptr')) != 'GLine': return None
        o = c['obj']; t0, t1 = o['m_endParams']
        A = (np.asarray(o['m_origin'], float) + np.asarray(o['m_dirVec'], float) * t0 - O) @ Mv.T
        Bp = (np.asarray(o['m_origin'], float) + np.asarray(o['m_dirVec'], float) * t1 - O) @ Mv.T
        d = (Bp - A)[:2]; L = float(np.linalg.norm(d))
        if L < 1e-9: return None
        d /= L; n = np.array([-d[1], d[0]])
        if ud.get('m_mirrored'): n = -n
        q = W / 4; D = W / ratio                 # step along, span of the zigzag across (2020 Residential: W 5.5", ratio 1.5)
        k = max(2, int(round(L / q))); q = L / k
        sL = -D / 2; sR = D / 2                  # zigzag between these lines; scallops join every second point on each side, bulging outwards
        P = lambda t, s_: (A[:2] + d * t + n * s_).tolist()
        def bez(c, m=10):
            u = np.linspace(0, 1, m)[:, None]; c = np.asarray(c, float)
            return ((1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u ** 2 * c[2] + u ** 3 * c[3]).tolist()
        def bsp(c, m=16):                        # clamped cubic B-spline, 5 control points, knots 0 0 0 0 1 2 2 2 2
            from scipy.interpolate import BSpline
            return BSpline(np.array([0, 0, 0, 0, 1, 2, 2, 2, 2.0]), np.asarray(c, float), 3)(np.linspace(0, 2, m)).tolist()
        loc = lambda pts: [P(t, s_) for t, s_ in pts]
        # phase: the pattern starts on the -n side at the lower end of the curve (2020 Residential wall run downwards: its end; 2020
        # Commercial parapet runs upwards: its start; both vs Revit's DXF splines); horizontal runs: the left end (?)
        lower_end = (Bp[1] < A[1] - 1e-9) or (abs(Bp[1] - A[1]) <= 1e-9 and Bp[0] < A[0])
        ph = k if lower_end else 0
        curves = []
        # points: cusp side at t = L - 2jq, scallop side at t = L - q - 2jq (anchored at the curve end as in Revit's export)
        for i in range(k):                       # segment between t_i = i q and t_i+1
            ta, tb = i * q, (i + 1) * q
            a_cusp = (ph - i) % 2 == 0          # point at ta on the -n side
            sa, sb = (sL, sR) if a_cusp else (sR, sL)
            c = (sb - sa) * 0.343
            curves.append(loc(bez([(ta, sa), (ta, sa + c), (tb, sb - c), (tb, sb)])))
        e1, e2 = 0.0786 * W, 0.2553 * W
        for side, sv in ((1, sR), (-1, sL)):
            pts = [i * q for i in range(k + 1) if ((ph - i) % 2 == 1) == (side == 1)]
            for ta, tb in zip(pts, pts[1:]):
                curves.append(loc(bsp([(ta, sv), (ta, sv + side * e1), ((ta + tb) / 2, sv + side * e2), (tb, sv + side * e1), (tb, sv)])))
            for t_r, t_end in ((pts[0], 0.0), (pts[-1], L)) if pts else ():
                if abs(t_r - t_end) < 1e-9: continue
                g = 1 if t_end > t_r else -1
                curves.append(loc(bez([(t_r, sv), (t_r, sv + side * e1), (t_r + g * 0.53 * q, sv + side * 0.166 * W), (t_end, sv + side * 0.166 * W)])))
        st = res.line(None, -2000077, 'proj', eid, annotation=False)
        return [{'t': 'line', 'pts': cv, 'style': st, 'elem': eid, 'layer': 'symbolic'} for cv in curves]

    def underlay_range(self, v, O, Z):
        r = v.get('range') or {}
        ub = r.get('underlay_bottom'); ut = r.get('underlay_top')
        if ub is None or ut is None or abs(ub) > 1e8 or abs(ut) > 1e8: return None
        lo, hi = sorted((ub - O[2], ut - O[2]))
        return lo, hi, (1.0 if Z[2] > 0 else -1.0)                     # heights above the origin; sign of the view depth axis (RCP: -1)

    def underlay(self, under, uw, px_mm, scale, res):
        """projected edges of underlay bodies (halftone), hidden-line removal among themselves"""
        out = []; clipped = []
        for eid, cid, uvw, fid, gs, ov in under:
            T = _clip_tris_halfspace(uvw, np.array([0, 0, 1.0]), uw[1])
            T = _clip_tris_halfspace(T, np.array([0, 0, -1.0]), -uw[0]) if len(T) else T
            if len(T): clipped.append((eid, cid, T, gs, ov))
        if not clipped: return out
        P = np.concatenate([c[2].reshape(-1, 3) for c in clipped])
        px = px_mm / 304.8 * scale
        db = DepthBuffer(P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max(), px)
        for c in clipped: db.add(c[2])
        for eid, cid, T, gs, ov in clipped:
            E = _feature_edges(T, None)
            vis = [(a, b) for a, b in db.visible_parts(E, px * 2.0) if np.hypot(*(b[:2] - a[:2])) > px * 0.5]
            if not vis: continue
            st = res.line(gs, cid, 'proj', eid, ov=dict(ov, halftone=True))
            out.append({'t': 'segs', 'segs': [[a[:2].tolist(), b[:2].tolist()] for a, b in vis], 'style': st, 'elem': eid, 'layer': 'underlay'})
            self.stats['underlay_elements'] += 1
        return out

    JOIN_CATS = {-2000011, -2000032, -2000035, -2000038, -2001300, -2000151}     # walls, floors, roofs, ceilings, structural foundations, ... clean up joins (?)

    def merge_cut_outlines(self, prims):
        """wall-join cleanup: cut regions of one category drawn with the same cut style are unioned, the shared boundaries disappear"""
        from shapely.ops import unary_union
        groups = collections.defaultdict(list); keep = []
        for p in prims:
            if p['t'] == 'cut' and p.get('cat') in self.JOIN_CATS and not p.get('fill'):
                st = p['style']; groups[(p['cat'], st['w'], tuple(st['rgb']), tuple(st['dash'] or ()))].append(p)
            else: keep.append(p)
        for k, ps in groups.items():
            regs = []; open_segs = []
            for p in ps:
                closed = [l for l in p['loops'] if len(l) > 3 and np.allclose(l[0], l[-1], atol=1e-6)]
                r = patterns.region(closed)
                if r is not None and len(closed) == len(p['loops']): regs.append(r.buffer(1e-5, join_style=2))
                else: keep.append(p)
            if not regs: continue
            u = unary_union(regs).buffer(-1e-5, join_style=2)
            segs = []; loops = []
            for poly in getattr(u, 'geoms', [u]):
                if poly.is_empty or poly.geom_type != 'Polygon': continue
                for ring in [poly.exterior] + list(poly.interiors):
                    c = list(ring.coords); loops.append([list(q) for q in c])
                    segs += [[list(a), list(b)] for a, b in zip(c, c[1:])]
            keep.append({'t': 'cut', 'loops': loops, 'segs': segs, 'style': ps[0]['style'], 'elem': ps[0]['elem'], 'elems': [p['elem'] for p in ps], 'cat': k[0], 'layer': 'cut'})
        return keep

    @staticmethod
    def _subtract_region(prims, region):
        """line / segs prims with the parts inside a shapely region removed"""
        from shapely.geometry import LineString
        out = []
        for p in prims:
            if p.get('t') == 'line' and p.get('pts') and len(p['pts']) > 1:
                d = LineString([tuple(q[:2]) for q in p['pts']]).difference(region)
                for g in getattr(d, 'geoms', [d]):
                    if g.geom_type == 'LineString' and not g.is_empty: out.append(dict(p, pts=[list(q) for q in g.coords]))
            elif p.get('t') == 'segs' and p.get('segs'):
                segs = []
                for a, b in p['segs']:
                    d = LineString([tuple(a[:2]), tuple(b[:2])]).difference(region)
                    for g in getattr(d, 'geoms', [d]):
                        if g.geom_type == 'LineString' and not g.is_empty: segs.append([list(g.coords[0]), list(g.coords[-1])])
                if segs: out.append(dict(p, segs=segs))
            else: out.append(p)
        return out

    def _underlay_occluder(self, v, O, Mv, elems, ztop):
        """plan-space union of the floors/roofs/ceilings of the view lying above z = ztop (shapely geometry or None), cached per (view, z band)"""
        cache = self.__dict__.setdefault('_uocc', {})
        key = (v['id'], round(ztop, 1))
        if key in cache: return cache[key]
        import rvt_elemmesh as E
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        polys = []
        for e in elems:
            inf = self.vis.info.info.get(e) or {}
            if inf.get('cat') not in (-2000032, -2000035, -2000038): continue          # floors, roofs, ceilings
            bb = self.vis.info.bbox(e)
            if bb is None or bb[0][2] < ztop - 1e-6 or bb[0][2] > (v['range'].get('top') or 1e9): continue
            try: T = np.asarray(E.element_mesh(self.f.g, e).get('tris') or [], float).reshape(-1, 3, 3)
            except Exception: continue
            for t in ((T - O) @ Mv.T)[:, :, :2]:
                pg = Polygon(t)
                if pg.is_valid and pg.area > 1e-6: polys.append(pg)
        cache[key] = unary_union(polys).buffer(0.01) if polys else None
        return cache[key]

    def _gs_hidden(self, ev, gs):
        """graphics style whose (sub)category is hidden in the view's V/G (Snowdon L2: structural framing 'Location Lines')"""
        if gs in (None, -1): return False
        hc = self.__dict__.get('_hid_cache')
        if hc is None or hc[0] is not ev:
            hc = (ev, self.vis.hidden_categories(self.vis.effective(ev))[0]); self._hid_cache = hc
        st = self.doc['gstyles'].get(gs)
        if not st: return False
        c = st.get('cat')
        return c in hc[1]

    def _elevation_swing(self, gs):
        c = self.__dict__.setdefault('_esw', {})
        if gs not in c:
            st = self.doc['gstyles'].get(gs) or {}
            c[gs] = ((self.doc['categories'].get(st.get('cat')) or {}).get('name') == 'Elevation Swing')
        return c[gs]

    def drawable_gs(self, gs):
        """geometry styled with an internal (non-API) category - wall layer/reference planes, location lines - is never drawn"""
        if gs in (None, -1): return True
        st = self.doc['gstyles'].get(gs)
        if not st: return True
        c = st.get('cat')
        if c == -2000083: return False          # family reference lines (green dashed, unnamed in projects: 2020 Residential elevation tag)
        return c is None or c >= 0 or c in CAT_TYPES or str(c) in self.dec.cat_names

    def text_note(self, eid, O, Mv, scale):
        """TextNote record -> text prim in view coordinates (origin model, sizes paper -> model by the view scale)"""
        r = self.f.rec(eid, 'TextNote')
        if not r: return None
        fl = r['fields']
        raw = (fl.get('m_oSavedRtfData') or {}).get('obj', {}).get('m_arrRtfStream')
        txt = gfx.rtf_text(raw) if raw is not None else ''
        tt = self.doc['text_types'].get(self.f.eid(fl.get('m_attrId'))) or {}
        font = self.doc['fonts'].get(tt.get('font')) or {}
        fl_ = fl.get('m_flags') or 0
        size = font.get('size') or 0.0078
        if raw is not None:
            fs = gfx.rtf_runs(raw).get('fs')
            if fs: size = fs / 2 / 72 / 12 * 0.72          # first run's em size (half points) -> Revit text size
        org = ((np.asarray(fl['m_orig'], float) - O) @ Mv.T)[:2].tolist()
        x = (Mv @ np.asarray(fl.get('m_baseVec') or [1, 0, 0], float))[:2].tolist()
        from .sheet import SheetComposer
        wid = (fl.get('m_lineWidth') or 0) * scale
        if wid and txt and not fl.get('m_bNoWrapping'): txt = wrap_text(txt, wid, size * scale / 0.72, font.get('name') or 'Arial', bool(tt.get('bold')))
        return {'t': 'text', 'text': txt, 'origin': org, 'x': x, 'size': size * scale, 'font': font.get('name') or 'Arial',
                'bold': tt.get('bold'), 'italic': tt.get('italic'), 'halign': SheetComposer._halign(fl_), 'valign': SheetComposer._valign(fl_), 'anchor': True,
                'elem': eid, 'layer': 'text', 'width': (fl.get('m_lineWidth') or 0) * scale}

    PART_DEFAULT = {'Grid': ('bubble', 'bubble'), 'Level': ('bubble', 'bubble'), 'IndependentTag': ('head', 'head'), 'RoomTag': ('head', 'head'), 'SpaceTag': ('head', 'head'),
                    'AreaTag': ('head', 'head'), 'InteriorElev': ('head', 'arrow'), 'Section': ('head', 'head'), 'SpotElevation': ('target', 'target'), 'TextNote': ('frame', 'frame')}
    PAPER_LAYERS = {'annotation', 'annotation_fill', 'text', 'datum'}

    def _finish(self, prims, O, Mv):
        """control-API keys on every prim (all optional for consumers, see CONTROL-API-ANSWERS.md): cat (category id of the owner element),
        paper (sizes are paper sizes: grow with the view scale), part (sub-part of the element: text | line | leader | arrow | witness | head | frame ...),
        anchor (world feet point the annotation sits at: its first point)"""
        info = self.vis.info.info; first = {}
        for p in prims:
            if '_tagged' in p and p['_tagged'] is None: del p['_tagged']
        lead = [p for p in prims if p.get('_tagged') is not None]
        if lead:                                                  # tag leaders end on the tagged element's drawn geometry, nearest to the tag head
            byel = {}
            for p in prims:
                if p.get('elem') is not None and p.get('layer') in ('cut', 'projection', 'symbolic', 'cut_fill', 'underlay') and p['t'] in ('line', 'segs', 'cut'):
                    byel.setdefault(p['elem'], []).append(p)
            for p in lead:
                tg = p.pop('_tagged'); pl = byel.get(tg)
                if not pl: continue
                h = np.asarray(p['pts'][-2], float); best = None
                for q in pl:
                    for sg in ([q['pts']] if q['t'] == 'line' else q['segs']):
                        A = np.asarray(sg, float)[:, :2]
                        for a_, b_ in zip(A[:-1], A[1:]):
                            ab = b_ - a_; L2 = float(ab @ ab)
                            t_ = 0.0 if L2 < 1e-12 else min(max(float((h - a_) @ ab) / L2, 0.0), 1.0)
                            c_ = a_ + ab * t_; dd = float(np.linalg.norm(c_ - h))
                            if best is None or dd < best[0]: best = (dd, c_)
                if best is not None: p['pts'][-1] = best[1].tolist()
        for p in prims:
            e = p.get('elem')
            if e is None: continue
            if 'cat' not in p:
                c = (info.get(e) or {}).get('cat')
                if c is not None and c != INVALID: p['cat'] = c
            p.setdefault('paper', p.get('layer') in self.PAPER_LAYERS)
            if 'part' not in p:
                lp, fp = self.PART_DEFAULT.get((info.get(e) or {}).get('cls'), ('line', 'fill'))
                p['part'] = 'text' if p['t'] == 'text' else fp if p['t'] == 'fill' else lp
            if p['paper'] and e not in first:
                q = p.get('origin') if p.get('origin') is not None else (p.get('pts') or [None])[0]
                if q is not None: first[e] = q
        Mi = np.linalg.inv(Mv)
        for p in prims:
            q = first.get(p.get('elem'))
            if q is not None and p['paper'] and 'anchor' not in p:
                p['anchor'] = (np.asarray([q[0], q[1], 0.0], float) @ Mi.T + O).tolist()
        return prims

    ZIGZAG = [(-0.0427, -0.0203), (-0.025, 0.0526), (0.025, -0.0536), (0.0427, 0.0193)]      # cut mark zigzag, paper inches about the diagonal's centre
    CUT_MARK_SLOPE = 0.4675                                                                  # 25 degrees (Residential and Commercial DXF)

    def stairs_symbol(self, eid, v, O, Mv, scale, res):
        """plan symbol of a straight single-run stair as Revit draws it (read off the DXF of 2020 Residential / Commercial): riser line + nosing line
        (1 in beyond) per boundary, stringer lines with end caps, and, when the cut plane crosses the stair, the cut mark (25 degree diagonal across
        the run with a zigzag at its centre) at boundary floor((cut - base - eps) / riser) - 1; boundaries before it are drawn as stairs below the
        cut (nosing lines dashed 'Overhead'), after it as stairs above (solid). A stair wholly below the cut inside the view range: all 'below'.
        Returns (prims, element ids replaced) or None when not handled (underlay stairs, several runs, landings)."""
        f = self.f; st = f.rec(eid, 'StairsElement'); sf = st['fields']
        runs = [f.eid(x) for c in (sf.get('m_cellList') or {}).get('obj', {}).get('m_cells', []) for x in (c.get('obj') or {}).get('m_runAndLandings') or []]
        sups = [f.eid(x) for c in (sf.get('m_cellList') or {}).get('obj', {}).get('m_cells', []) for x in (c.get('obj') or {}).get('m_supports') or []]
        if len(runs) != 1 or not f.rec(runs[0], 'StairsRun'): return None
        rf = f.rec(runs[0])['fields']
        s0 = np.asarray(ob(rf['m_oStartRiser'])['m_origin'], float); s1 = np.asarray(ob(rf['m_oEndRiser'])['m_origin'], float)
        nrs = int(sf.get('m_actualNumberOfRisers') or 0); rh = float(sf.get('m_actualRiserHeight') or 0.0)
        zb = float(rf.get('m_bottomElevation') or 0.0); zt = zb + float(sf.get('m_stairsHeight') or 0.0)
        L = float(np.linalg.norm((s1 - s0)[:2]))
        rg = v.get('range') or {}
        cut = rg.get('cut'); depth = rg.get('depth')
        if nrs < 2 or L < 1e-6 or not rh or cut is None or depth is None: return None
        if zb < cut < zt: kb = max(math.floor((cut - zb - 1e-6) / rh) - 1, 0)
        elif zt <= cut and zb >= depth - 1e-6: kb = None
        else: return None
        half = float(rf.get('m_actualRunWidth') or 0.0) / 2
        if half <= 0: return None
        sw = float(rf.get('m_leftStringerWidth') or 2 / 12)
        tread = L / (nrs - 1)
        P = lambda p: ((np.asarray(p, float) - O) @ Mv.T)[:2]
        a, b = P(s0), P(s1); d = (b - a) / np.linalg.norm(b - a)
        if abs(d[0]) > 1e-3: return None                      # runs along the view's x: cut mark orientation not read off yet
        sg = 1.0 if d[1] > 0 else -1.0
        cx = a[0]; xl, xr = cx - half, cx + half; xol, xor_ = cx - half - sw, cx + half + sw
        cat = -2000921
        st_solid = res.line(None, cat, 'proj', eid, annotation=False)
        st_dash = res.line(None, cat, 'proj', eid, annotation=False, ov={'proj_pattern': self._overhead_pattern()})
        nos = 1 / 12.0; K = self.CUT_MARK_SLOPE
        cy = a[1] + sg * kb * tread if kb is not None else None
        out = []
        def seg(p0, p1, style, part='tread'):
            if np.linalg.norm(np.asarray(p1) - np.asarray(p0)) > 1e-6:
                out.append({'t': 'line', 'pts': [np.asarray(p0, float).tolist(), np.asarray(p1, float).tolist()], 'style': style, 'elem': eid, 'layer': 'symbolic', 'part': part})
        def is_above(x, y): return (y - (cy + (x - cx) * K)) * sg > 0          # beyond the cut mark, toward the top of the stair
        def across(y, below_style):
            if kb is None: seg((xl, y), (xr, y), below_style); return
            ya, yb = is_above(xl, y), is_above(xr, y)
            if ya and yb: seg((xl, y), (xr, y), st_solid); return
            if not ya and not yb: seg((xl, y), (xr, y), below_style); return
            xs = cx + (y - cy) / K; gx = 0.0427 * scale / 12.0
            near = abs(y - cy) < 0.0536 * scale / 12.0
            lo, hi = (xs - gx, xs + gx) if near else (xs, xs)
            seg((xl, y), (lo, y), st_solid if ya else below_style); seg((hi, y), (xr, y), below_style if ya else st_solid)
        for i in range(nrs):
            y = a[1] + sg * i * tread
            across(y, st_solid)
            if i < nrs - 1: across(y + sg * nos, st_dash if (kb is None or i < kb) else st_solid)
        for x in (xl, xr, xol, xor_):                          # stringer lines: below the cut mark one style, above another (both solid here)
            if kb is None: seg((x, a[1]), (x, b[1]), st_solid, 'stringer')
            else:
                yd = min(max(cy + (x - cx) * K, min(a[1], b[1])), max(a[1], b[1]))
                seg((x, a[1]), (x, yd), st_solid, 'stringer'); seg((x, yd), (x, b[1]), st_solid, 'stringer')
        for y in (a[1], b[1]):
            seg((xl, y), (xol, y), st_solid, 'stringer'); seg((xr, y), (xor_, y), st_solid, 'stringer')
        if kb is not None:                                     # cut mark: diagonal with a zigzag at its centre
            zig = [(cx + zx * scale / 12.0, cy + zy * scale / 12.0) for zx, zy in self.ZIGZAG]
            seg((xol, cy + (xol - cx) * K), zig[0], st_solid, 'cutmark')
            for k in range(3): seg(zig[k], zig[k + 1], st_solid, 'cutmark')
            seg(zig[3], (xor_, cy + (xor_ - cx) * K), st_solid, 'cutmark')
        return out, set(runs) | set(sups) | {eid}

    def _overhead_pattern(self):
        for k, lp in self.doc['line_patterns'].items():
            if str(lp.get('name')) in ('Overhead 1/16"', 'Overhead'): return k
        return None

    def stairs_path(self, eid, v, O, Mv, scale, res, cat):
        """stair path (StairsPathElement): line along the run centre with an open 90 degree arrow (type's arrowhead) and UP / DN text.
        Rules read off Revit's DXF (Residential + Commercial, 7 views): the path stops m_distanceToCutMark (1/8" paper) before the break line;
        the break sits at the riser line floor((4 ft - eps) / riser) - 1 treads from the run start (4 ft = the view's cut offset above the stair base);
        a stair that is only in the underlay (below the view range depth) shows UP over its whole length; a stair inside the range but wholly
        below the cut shows DN from the top end, as long as the same 4 ft rule gives; texts: UP centred under the start (gap 5.3 model inches),
        DN left of the top end (9 model inches)."""
        f = self.f; r = f.rec(eid, 'StairsPathElement'); fl = r['fields']
        stid = f.eid(fl['m_stairsLinkElementId']['m_linkInstOrHostId'])
        st = f.rec(stid); sf = st['fields']
        runs = [f.eid(x) for c in (sf.get('m_cellList') or {}).get('obj', {}).get('m_cells', []) for x in (c.get('obj') or {}).get('m_runAndLandings') or []]
        runs = [x for x in runs if f.rec(x, 'StairsRun')]
        if len(runs) != 1: return []
        rf = f.rec(runs[0])['fields']
        s0 = np.asarray(ob(rf['m_oStartRiser'])['m_origin'], float); s1 = np.asarray(ob(rf['m_oEndRiser'])['m_origin'], float)
        nrs = int(sf.get('m_actualNumberOfRisers') or 0); rh = sf.get('m_actualRiserHeight') or 0.5
        zb = float(rf.get('m_bottomElevation') or 0.0); zt = zb + float(sf.get('m_stairsHeight') or 0.0)
        L = float(np.linalg.norm((s1 - s0)[:2]))
        if nrs < 2 or L < 1e-6: return []
        tread = L / (nrs - 1)
        rg = v.get('range') or {}
        cut = rg.get('cut'); depth = rg.get('depth'); off = (rg.get('offsets') or [4.0])[0] or 4.0
        if cut is None: return []
        gap = (path(f.rec(f.eid(fl.get('m_typeId')))['fields'], 'm_distanceToCutMark') or 0.0104167) * scale
        P = lambda p: ((np.asarray(p, float) - O) @ Mv.T)[:2]
        a, b = P(s0), P(s1); d = b - a; d /= np.linalg.norm(d)
        cutcase = False
        if zb < cut < zt:                                   # crossed by the cut plane: UP to the break
            up = True; cutcase = True
            n = max(math.floor((cut - zb - 1e-6) / rh) - 1, 0)
            p_start, p_end = a, a + d * max(n * tread * 1.0 - gap, 0.0)
        elif depth is not None and zb >= depth - 1e-6 and zt <= cut:     # inside the range, wholly below the cut: DN from the top
            up = False
            n = max(math.floor((off - 1e-6) / rh) - 1, 0)
            ln = L if (zt - zb) <= off else min(L, n * tread)
            p_start, p_end = b, b - d * ln
        else:                                               # underlay: UP over the whole run
            up = True; p_start, p_end = a, b
        dd = (p_end - p_start) / (np.linalg.norm(p_end - p_start) or 1.0)
        st_ = res.line(None, cat, 'proj', eid, annotation=True)
        out = [{'t': 'line', 'pts': [p_start.tolist(), p_end.tolist()], 'style': st_, 'elem': eid, 'layer': 'annotation', 'part': 'line'}]
        al = 1 / 16 * IN * scale
        nrm = np.array([-dd[1], dd[0]])
        for sg in (1, -1):
            out.append({'t': 'line', 'pts': [p_end.tolist(), (p_end - dd * al + nrm * sg * al).tolist()], 'style': st_, 'elem': eid, 'layer': 'annotation', 'part': 'arrow'})
        tt = self.doc['text_types'].get(f.eid(path(f.rec(f.eid(fl.get('m_typeId')))['fields'], 'm_textTypeId'))) or {}
        font = self.doc['fonts'].get(tt.get('font')) or {}
        size = (font.get('size') or 3 / 32 * IN) * scale
        txt = fl.get('m_upText') if up else fl.get('m_downText')
        if txt and (fl.get('m_showUpText') if up else fl.get('m_showDownText')):
            if cutcase:     # centred beyond the start, 5.3 model inches clear of the run (box top edge on the far side)
                c = p_start - dd * (5.3 / 12 + size / 2)
                org = np.array([c[0], c[1] + size / 2]); halign = 1
            else:           # whole-run / DN paths: left of the start, 0.185" paper, box top 0.048" paper above it (Residential DXF at 1:48 and 1:96)
                org = np.array([p_start[0] - 0.185 * IN * scale, p_start[1] + 0.048 * IN * scale]); halign = 0
            out.append({'t': 'text', 'text': txt, 'origin': org.tolist(), 'x': [1.0, 0.0], 'size': size, 'font': font.get('name') or 'Arial', 'halign': halign, 'valign': 0,
                        'anchor': True, 'elem': eid, 'layer': 'text', 'part': 'text'})
        return out

    def _region_rgb(self, gs, res):
        st = res.line(gs, None, 'proj', None)
        return list(st.get('rgb') or [0, 0, 0]) if st else None

    def text_note_leaders(self, eid, O, Mv, scale, res, cat):
        """text note leaders: anchor -> elbow -> end (polyline) or, with m_bArcLeaders, the circle arc through the three points; arrow head
        of the text type's leader style (Arrow 30 Degree: full angle in param -4293960870.., size on paper) at the end"""
        r = self.f.rec(eid, 'TextNote'); fl = r['fields']
        leaders = fl.get('m_leaders') or []
        out = []
        tt0 = self.f.rec(self.f.eid(fl.get('m_attrId'))) or {}
        tf0 = tt0.get('fields') or {}
        if tf0.get('m_textBoxVisibility') and fl.get('m_orig') and (fl.get('m_trueWidth') or fl.get('m_lineWidth')) and fl.get('m_height'):
            # type 'show border': box around the text, margin = the type's leader offset (paper), width / height = the note's (paper) x scale
            # (Commercial Level 1 'Store fixture layout by store owner': 118 x 59 in = text 103 x 44 + 2 x 7.65 at 1:96)
            gs0 = ((self.f.rec(self.f.eid((tf0.get('m_lineAndTextAttr') or {}).get('m_categoryId'))) or {}).get('fields') or {}).get('m_gstyleIds') or [None]
            mg = (tf0.get('m_leaderOffsetSheet') or 0.0) * scale
            org_ = ((np.asarray(fl['m_orig'], float) - O) @ Mv.T)[:2]
            xv = (Mv @ np.asarray(fl.get('m_baseVec') or [1, 0, 0], float))[:2]; yv = (Mv @ np.asarray(fl.get('m_upVec') or [0, 1, 0], float))[:2]
            w = (fl.get('m_trueWidth') or fl.get('m_lineWidth')) * scale; h = fl['m_height'] * scale
            cs = [org_ + xv * (-mg) + yv * mg, org_ + xv * (w + mg) + yv * mg, org_ + xv * (w + mg) - yv * (h + mg), org_ + xv * (-mg) - yv * (h + mg)]
            out.append({'t': 'line', 'pts': [q.tolist() for q in cs + [cs[0]]], 'style': res.line(gs0[0], cat, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation', 'part': 'frame'})
        if not leaders: return out
        P = lambda p: ((np.asarray(p, float) - O) @ Mv.T)[:2]
        tt = self.f.rec(self.f.eid(fl.get('m_attrId'))) or {}
        tf = tt.get('fields') or {}
        gs = ((self.f.rec(self.f.eid((tf.get('m_lineAndTextAttr') or {}).get('m_categoryId'))) or {}).get('fields') or {}).get('m_gstyleIds') or [None]
        st = res.line(gs[0], cat, 'proj', eid, annotation=True)
        ang = 30 * math.pi / 180; size = 1 / 8 * IN * scale
        ls = self.f.rec(self.f.eid(next((x.get('m_value') for x in (path(tf, 'm_pParamValueSetElementId', 'm_paramSet') or []) if x.get('m_paramId') == 4293960981), None)))
        if ls:
            for x in path(ls['fields'], 'm_pParamValueSetDouble', 'm_paramSet') or []:
                if x.get('m_paramId') == 4293960870: ang = x['m_value']
                elif x.get('m_paramId') == 4293960882: size = x['m_value'] * scale
        for lo in leaders:
            l = lo.get('obj') or lo
            if not l.get('m_end'): continue
            a, e = P(l['m_anchor']), P(l['m_end']); el = P(l.get('m_elbow') or l['m_anchor'])
            pts = [a, el, e]
            if fl.get('m_bArcLeaders') and not l.get('m_bStraight'):
                pts = _arc3(a, el, e) or pts
            out.append({'t': 'line', 'pts': [q.tolist() for q in pts], 'style': st, 'elem': eid, 'layer': 'annotation', 'part': 'leader'})
            if (l.get('m_type') or 0) != 0:
                u = pts[-2] - pts[-1]; n_ = np.linalg.norm(u)
                if n_ > 1e-9:
                    u /= n_; ca, sa = math.cos(ang / 2), math.sin(ang / 2)
                    arm = size / ca
                    for sg in (1, -1):
                        v = np.array([u[0] * ca - sg * u[1] * sa, u[1] * ca + sg * u[0] * sa]) * arm
                        out.append({'t': 'line', 'pts': [e.tolist(), (e + v).tolist()], 'style': st, 'elem': eid, 'layer': 'annotation', 'part': 'arrow'})
        return out

    def materials(self):
        if getattr(self, '_mat', None) is None:
            try:
                import rvt_materials
                self._mat = rvt_materials.material_table(self.f.fn)
            except Exception: self._mat = {}
        return self._mat

    HOST_CATS = {-2000011, -2000032, -2000035, -2000038, -2000040}       # walls, floors, roofs, ceilings, ? (compound structures)

    def _compound_of(self, eid):
        r = self.f.rec(eid)
        if not r: return None
        import re as _re
        for k_, v_ in r['fields'].items():
            if _re.fullmatch(r'm_\w*Attr(ibutes)?Id', k_) and v_ is not None:
                t = self.f.rec(self.f.eid(v_))
                cs = ob((t or {}).get('fields', {}).get('m_pCompoundStructure')) if t else None
                if cs: return cs
        return None

    def cut_fill(self, eid, cid, gs, ov, detail):
        """cut pattern of an element: override > coarse fill of the type (coarse detail, host objects) > material of the cut body > category material"""
        if ov.get('cut_fg_visible') is False: return None
        if ov.get('cut_fg_pattern') is not None: return {'pattern': ov['cut_fg_pattern'], 'color': ov.get('cut_fg_color') or [0, 0, 0]}
        info = self.vis.info.info.get(eid) or {}
        if detail == 1 and cid in self.HOST_CATS:            # coarse: host objects show their type's coarse fill (or nothing); families keep material patterns
            cs_ = self._compound_of(eid)
            if cs_ is not None:                              # the coarse fill lives in the type's compound structure (basement concrete walls)
                pid_ = self.f.eid(cs_.get('m_coarseScaleFillPatternElemId'))
                if pid_ not in (None, -1, INVALID): return {'pattern': pid_, 'color': self._rgb(cs_.get('m_coarseScaleFillColor')) or [0, 0, 0]}
            t = self.type_params(eid)
            if t is not None:
                pid = t.get(-1002106)
                if pid not in (None, -1): return {'pattern': pid, 'color': self._rgb(t.get(-1002110)) or [0, 0, 0]}
                return None
        st = self.doc['gstyles'].get(gs) or {}
        mid = ov.get('_mat')                                  # material of the cut body's faces (compound layers, families)
        if mid in (None, -1): mid = st.get('material', -1)
        if mid in (None, -1): mid = ((self.doc['categories'].get(cid) or {}).get('proj') or {}).get('material', -1)
        m = self.materials().get(mid) if mid not in (None, -1) else None
        cp = (m or {}).get('cut_pattern') or {}
        if cp.get('id') is not None: return {'pattern': cp['id'], 'color': cp.get('color') or [0, 0, 0]}
        return None

    @staticmethod
    def _rgb(v):
        from .decode import color
        return color(v) if isinstance(v, int) else v

    def topo_boundary(self, eid, cid, ov, O, Mv, res, prims):
        """plan views: the outline of a topography surface (edges used by one triangle of its mesh: outer boundary, sub-region and pad holes) as lines in the
        Topography style; Revit's plan shows no contours here (Residential first floor DXF C-TOPO: the site rectangle, pad / driveway / path outlines)"""
        import rvt_elemmesh as E
        m = E.element_mesh(self.f.g, eid)
        T = np.asarray(m.get('tris') or [], float).reshape(-1, 3, 3)
        if not len(T): return
        key = lambda p: (round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[2]), 4))
        cnt = collections.Counter(); ends = {}
        for t in T:
            for a, b in ((0, 1), (1, 2), (2, 0)):
                ka, kb = key(t[a]), key(t[b]); k = (ka, kb) if ka < kb else (kb, ka)
                cnt[k] += 1; ends[k] = (t[a], t[b])
        segs = [ends[k] for k, n in cnt.items() if n == 1]
        if not segs: return
        st = res.line(None, cid, 'proj', eid, ov=ov)
        uv = [(((np.asarray(a) - O) @ Mv.T)[:2], ((np.asarray(b) - O) @ Mv.T)[:2]) for a, b in segs]
        for pl in self._loops([(np.append(a, 0.0), np.append(b, 0.0)) for a, b in uv], 1e-4):
            P = np.asarray(pl, float)[:, :2]
            if len(P) > 1: prims.append({'t': 'line', 'pts': P.tolist(), 'style': st, 'elem': eid, 'layer': 'projection'})
        self.stats['topo_boundary'] += 1

    def topo_poche(self, eid, cid, ov, O, Mv, cut_w, scale, res, prims, crop=None):
        """topography cut by a section: the surface mesh (reader polymesh) meets the cut plane in a profile; Revit fills below it down to
        the poche base with the site material's cut pattern (SiteSettings poche base not decoded: 30 ft below the lowest profile point,
        the viewport crop cuts it). Returns the poche loops (added to the hidden-line caps)."""
        import rvt_elemmesh as E
        m = E.element_mesh(self.f.g, eid)                       # the reader adapter's saved-graphics index (one per file)
        T = np.asarray(m.get('tris') or [], float).reshape(-1, 3, 3)
        if not len(T): return []
        uvw = (T - O) @ Mv.T
        segs = _plane_section(uvw, np.array([0, 0, 1.0]), cut_w)
        if not segs: return []
        loops = []
        st = res.line(None, cid, 'cut', eid, ov=ov)
        mats = self.materials()
        mid = next((k for k, v in mats.items() if 'earth' in str(v.get('name', '')).lower()), None)
        cp = (mats.get(mid) or {}).get('cut_pattern') or {}
        for pl in self._loops(segs, 1e-5):
            P = np.asarray(pl, float)[:, :2]
            if len(P) < 2: continue
            if P[0, 0] > P[-1, 0]: P = P[::-1]
            base = P[:, 1].min() - 30.0
            if crop is not None:                                    # poche stops at the crop region (also bounds hatch size on big surfaces)
                P = _clip_polyline_u(P, crop[0] - 1, crop[2] + 1) if len(P) > 2 else P
                if len(P) < 2: continue
                base = max(base, crop[1] - 1)
            loop = P.tolist() + [[P[-1, 0], base], [P[0, 0], base], P[0].tolist()]
            loops.append(loop)
            prims.append({'t': 'line', 'pts': P.tolist(), 'style': st, 'elem': eid, 'layer': 'cut'})
            pat = self.doc['fill_patterns'].get(cp.get('id')) if cp.get('id') is not None else None
            if pat:
                reg = patterns.region([loop])
                if reg is not None and not pat.get('solid'):
                    prims.append({'t': 'segs', 'segs': patterns.hatch(reg, pat, scale), 'style': {'w': 0.1, 'rgb': cp.get('color') or [0, 0, 0], 'dash': None}, 'elem': eid, 'layer': 'cut_fill'})
        self.stats['topo_poche'] += len(loops)
        return [loops]

    def color_schema(self, v):
        """{param value: (rgb, pattern id)} of the colour scheme applied to rooms in view v (DBView.m_pColorFillSchemaSetting
        m_categoryToSchema -> ColorFillSchema.m_colorFillArr; entries keyed by the parameter's stored value), or None"""
        r = self.f.rec(v['id'])
        st = ob_((r or {'fields': {}})['fields'].get('m_pColorFillSchemaSetting')) or {}
        for e in st.get('m_categoryToSchema') or []:
            cat = e.get('first'); cat = cat - 2 ** 32 if isinstance(cat, int) and cat >= 2 ** 31 else cat
            if cat != -2000160: continue
            sch = self.f.rec(self.f.eid(e.get('second')))
            if not sch: continue
            pid = sch['fields'].get('m_paramId'); pid = self.f.eid(pid) if pid is not None else None
            if isinstance(pid, int) and pid >= 2 ** 31: pid -= 2 ** 32
            out = {}
            for it in sch['fields'].get('m_colorFillArr') or []:
                if it.get('m_bHidden') or not it.get('m_bInUse', 1) or it.get('m_isPlaceholder'): continue
                ps = it.get('m_paramStorage') or {}
                key = ob_(ps.get('m_str')) if isinstance(ob_(ps.get('m_str')), str) else (ps.get('m_str') or {}).get('m_str') if isinstance(ps.get('m_str'), dict) else ps.get('m_str')
                col = it.get('m_color') or 0
                out[key] = ([col & 255, (col >> 8) & 255, (col >> 16) & 255], self.f.eid(it.get('m_fillPatternId')))
            return {'param': pid, 'entries': out}
        return None

    def _opening_boxes(self, elems, O, Mv):
        """{host wall id: [(lo, hi) boxes in view coordinates]} of the doors / windows hosted by each wall (m_hostId)"""
        boxes = {}
        for e in elems:
            inf = self.vis.info.info.get(e) or {}
            if inf.get('cls') != 'FamilyInstance' or inf.get('cat') not in (-2000023, -2000014): continue
            r = self.f.rec(e)
            hid = self.f.eid(r['fields'].get('m_hostId')) if r else None
            bb = self.vis.info.bbox(e)
            if hid in (None, INVALID) or bb is None: continue
            lo, hi = np.asarray(bb[0], float), np.asarray(bb[1], float)
            C = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            Q = (C - O) @ Mv.T
            boxes.setdefault(hid, []).append((Q.min(0), Q.max(0)))
        return boxes

    def _carve_tris(self, T, bxs):
        """door / window openings are not part of the saved wall solids: cut the projected box of every hosted opening out of the wall's view-facing
        (constant depth) triangles whose depth lies inside the box, so sections and elevations see through the opening"""
        from shapely.geometry import Polygon, box as sbox
        import mapbox_earcut as earcut
        out = []; keep = np.ones(len(T), bool)
        for lo, hi in bxs:
            tmin = T[:, :, :2].min(1); tmax = T[:, :, :2].max(1); wm = T[:, :, 2].mean(1)
            cand = np.where(keep & (tmax[:, 0] > lo[0]) & (tmin[:, 0] < hi[0]) & (tmax[:, 1] > lo[1]) & (tmin[:, 1] < hi[1]) & (wm > lo[2] - 0.08) & (wm < hi[2] + 0.08))[0]
            rect = sbox(lo[0], lo[1], hi[0], hi[1])
            for i in cand:
                t = T[i]
                if np.ptp(t[:, 2]) > 0.02: continue
                pg = Polygon(t[:, :2])
                if pg.area < 1e-9: continue
                d = pg.difference(rect)
                if d.equals(pg): continue
                keep[i] = False
                for g in getattr(d, 'geoms', [d]):
                    if g.geom_type != 'Polygon' or g.area < 1e-9: continue
                    rings = [list(g.exterior.coords)[:-1]] + [list(q.coords)[:-1] for q in g.interiors]
                    verts = np.array([q for r_ in rings for q in r_], float); ends = np.cumsum([len(r_) for r_ in rings]).astype(np.uint32)
                    idx = earcut.triangulate_float64(verts, ends).reshape(-1, 3)
                    tt = np.zeros((len(idx), 3, 3)); tt[:, :, :2] = verts[idx]; tt[:, :, 2] = float(t[:, 2].mean())
                    out.append(tt)
        return np.concatenate([T[keep]] + out) if out else T[keep]

    def rebar_bars(self, eid, curves):
        """every bar of a Rebar set / area-path reinforcement bar set as its centre-line polylines (reader: rvt_rebar.rebar_centerlines; the saved graphics of
        these elements are only the bounding diagonal of the set)"""
        import rvt_rebar
        res = rvt_rebar.rebar_centerlines(self.f.fn, eid)
        if not res or not res.get('bars'): return None
        gs = curves[0].get('gs') if curves else None
        out = []
        for bar in res['bars']:
            for cv in bar:
                if cv['type'] == 'line': pts = np.array([cv['p0'], cv['p1']], float)
                else:
                    C = np.asarray(cv['center'], float); X = np.asarray(cv['xvec'], float); Y = np.asarray(cv['yvec'], float); r = cv['radius']
                    th = np.linspace(cv['t0'], cv['t1'], 9)
                    pts = np.array([C + r * (math.cos(t) * X + math.sin(t) * Y) for t in th])
                out.append({'pts': pts, 'gs': gs})
        return out

    def _label_param_ids(self):
        c = self.__dict__.get('_lblp')
        if c is None:
            c = self._lblp = set()
            for r in self.f.recs('ParamElemFamily'):
                d = (ob_(r['fields'].get('m_pParamDef')) or {})
                if d.get('m_caption') == 'Label': c.add(r['id'])
        return c

    def family_label(self, eid, O, Mv, scale):
        """family text label bound to the string parameter 'Label' ('REF.', 'DW' of appliances): the label element is not in the saved symbol graphics;
        Revit draws it 3/32\" Arial centred on the symbol's bounding box (2020 Residential plan 32 DXF A-ANNO-NOTE)"""
        ids = self._label_param_ids()
        if not ids: return []
        r = self.f.rec(eid)
        fl = r['fields']; sym = self.f.eid(fl.get('m_masterSymbolId'))
        if sym in (None, 4294967295): return []
        txt = None
        for rec in (self.f.rec(sym), self.f.rec(self.f.eid((self.f.rec(sym) or {'fields': {}})['fields'].get('m_familyId'))) if False else None):
            if not rec: continue
            for k, val in self.tags.fam_values(rec).items():
                if int(k) in ids and isinstance(val, str) and val.strip(): txt = val.strip(); break
            if txt: break
        if not txt: return []
        gb = (self.f.g.res.get(sym) or {}).get('bbox')
        trf = (ob_(fl.get('m_pInstanceInfo')) or {}).get('m_Trf') or {}
        if not gb or not trf.get('m_3x3'): return []
        M = np.asarray(trf['m_3x3'], float); o = np.asarray(trf['m_or'], float)
        ctr = o + M @ ((np.asarray(gb[0], float) + np.asarray(gb[1], float)) / 2)
        uv = ((ctr - O) @ Mv.T)[:2]
        font = self.doc['fonts'].get(next(iter(self.doc['fonts']), None)) or {}
        return [{'t': 'text', 'text': txt, 'origin': uv.tolist(), 'x': [1.0, 0.0], 'size': 3 / 32 / 12 * scale, 'font': 'Arial', 'halign': 1, 'valign': 1,
                 'anchor': True, 'elem': eid, 'layer': 'text'}]

    def stairs_path_text(self, eid, O, Mv, scale, v):
        """'UP' at the start riser of a run that starts at the view's level, 'DN' at the end riser of a run that ends there: baseline-left text at the
        riser midpoint + (-3/16\", +0.047\") x scale + the path's text offset (2020 Residential plan 32: all four DN, Commercial plan 32 UP, DXF S-STRS-IDEN)"""
        if v['kind'] != 'plan': return []
        r = self.f.rec(eid, 'StairsPathElement'); fl = r['fields']
        lk = ob_(fl.get('m_stairsLinkElementId')) or {}; sid = self.f.eid(lk.get('m_linkInstOrHostId'))
        out = []
        typ = self.f.rec(self.f.eid(fl.get('m_typeId')))
        la = ob_((typ['fields'] if typ else {}).get('m_pLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        size = (font.get('size') or 3 / 32 / 12) * scale
        for run in self.f.recs('StairsRun'):
            rf = run['fields']
            if self.f.eid(rf.get('m_stairsId')) != sid: continue
            def mid(c):
                o = ob_(rf[c]); a = np.asarray(o['m_origin'], float); d = np.asarray(o['m_dirVec'], float); t0, t1 = o['m_endParams']
                return (a + d * (t0 + t1) / 2)
            bot, top = rf.get('m_bottomElevation'), rf.get('m_topElevation')
            for key, txt_k, show_k, which, off_k in (('m_oStartRiser', 'm_upText', 'm_showUpText', 'bot', 'm_upTextOffset'), ('m_oEndRiser', 'm_downText', 'm_showDownText', 'top', 'm_downTextOffset')):
                lvl = bot if which == 'bot' else top
                if not fl.get(show_k) or lvl is None or abs(float(lvl) - float(self.level_elevation(v, O))) > 0.05 or not fl.get(txt_k): continue
                off = np.asarray((ob_(fl.get(off_k)) or {}).get('m_xyz') or [0, 0, 0], float)
                p = mid(key) + off + np.array([-3 / 16 / 12 * scale, 0.047 / 12 * scale, 0.0])
                uv = ((p - O) @ Mv.T)[:2]
                out.append({'t': 'text', 'text': fl[txt_k], 'origin': uv.tolist(), 'x': [1.0, 0.0], 'size': size, 'font': font.get('name') or 'Arial', 'halign': 0, 'valign': 2,
                            'anchor': True, 'elem': eid, 'layer': 'text'})
        return out

    def level_elevation(self, v, O):
        return O[2]

    def property_line(self, eid, O, Mv, res, v):
        """property line segment (site plans): its GLine / GArc curve in the 'Property Lines' category style (dash-dot pattern, pen 8)"""
        if v['kind'] != 'plan' or -2001265 in self.vis.hidden_categories(self.vis.effective(v))[0]: return []
        r = self.f.rec(eid, 'PropertyLineSegment')
        c = r['fields'].get('m_curve') if r else None
        if not c: return []
        cls = self.f.tagname(c.get('ptr')); o = ob_(c)
        if cls == 'GLine':
            orr = np.asarray(o['m_origin'], float); d = np.asarray(o['m_dirVec'], float); t0, t1 = o['m_endParams']
            P = np.array([orr + d * t0, orr + d * t1])
        elif cls == 'GArc':
            from .gfx import arc_pts
            t0, t1 = o['m_endParams']
            P = np.asarray(arc_pts(o['m_center'], o['m_radius'], o['m_xVec'], o['m_yVec'], t0, t1), float)
        else: return []
        pts = ((P - O) @ Mv.T)[:, :2]
        st = res.line(None, -2001265, 'proj', eid)
        return [{'t': 'line', 'pts': pts.tolist(), 'style': st, 'elem': eid, 'layer': 'projection'}]

    def color_legend(self, eid, v, O, Mv, scale):
        """colour scheme legend (ColorFillLegend): title above the origin (top-left of the first row), one row per scheme entry in alphabetical order:
        3/8\" swatch + text 1/10\" right of it, rows 1/8\" apart (2020 Commercial plan 32 DXF G-ANNO-LEGN: swatch 36 in, pitch 48 in at 1:96)"""
        r = self.f.rec(eid, 'ColorFillLegend')
        sch = None
        for e in (ob_((self.f.rec(v['id']) or {'fields': {}})['fields'].get('m_pColorFillSchemaSetting')) or {}).get('m_categoryToSchema') or []:
            sch = self.f.rec(self.f.eid(e.get('second')))
            cat = e.get('first'); cat = cat - 2 ** 32 if isinstance(cat, int) and cat >= 2 ** 31 else cat
            if self.f.eid(r['fields'].get('m_idSchemeCategory')) in (cat, cat + 2 ** 32): break
        if not sch: return []
        sym = self.f.rec(self.f.eid(r['fields'].get('m_symbolId')))
        sf = sym['fields'] if sym else {}
        la = ob_(sf.get('m_oLineAndTextAttr')) or {}; tla = ob_(sf.get('m_oTitleLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}; tfont = self.doc['fonts'].get(self.f.eid(tla.get('m_fontId'))) or {}
        size = (font.get('size') or 3 / 16 / 12) * scale; tsize = (tfont.get('size') or size / scale * 1.5) * scale
        sw = 3 / 8 / 12 * scale; gap = 1 / 8 / 12 * scale; tx = 0.1 / 12 * scale
        o = ((np.asarray(r['fields']['m_origin'], float) - O) @ Mv.T)[:2]
        wid = (ob_(r['fields'].get('m_oLayout')) or {}).get('m_columnWidths', [2 / 12])[0] * scale
        from .annot import Tags
        ents = []
        for it in sch['fields'].get('m_colorFillArr') or []:
            if it.get('m_bHidden') or not it.get('m_bInUse', 1) or it.get('m_isPlaceholder'): continue
            ps = it.get('m_paramStorage') or {}
            key = ps.get('m_str')
            if isinstance(key, dict): key = (ob_(key) or key).get('m_str') if 'obj' in key else key.get('m_str')
            name = it.get('m_caption') if not it.get('m_bDefaultCaption', 1) and it.get('m_caption') else key
            col = it.get('m_color') or 0
            if name: ents.append((str(name), [col & 255, (col >> 8) & 255, (col >> 16) & 255]))
        ents.sort(key=lambda x: x[0].lower())
        cid = self.f.eid(r['fields'].get('m_idSchemeCategory')); cid = cid - 2 ** 32 if cid >= 2 ** 31 else cid
        out = [{'t': 'text', 'text': {-2000160: 'Room Legend', -2003600: 'Space Legend'}.get(cid, 'Legend'),
                'origin': [o[0], o[1] + 0.0489 * scale], 'x': [1.0, 0.0], 'size': tsize, 'font': tfont.get('name') or 'Arial', 'halign': 0, 'valign': 0, 'anchor': True, 'elem': eid, 'layer': 'text'}]
        top = o[1]; line = {'w': 0.0762, 'rgb': [0, 0, 0], 'dash': None, 'pen': 1, 'halftone': False}
        for name, rgb in ents:
            txt = wrap_text(name, max(wid - sw - 2 * tx, 0.01), size / 0.72, font.get('name') or 'Arial')
            n = txt.count('\n') + 1
            rh = max(sw, n * size / 0.72 * 1.24)
            sq = [[o[0], top], [o[0] + sw, top], [o[0] + sw, top - sw], [o[0], top - sw], [o[0], top]]
            out.append({'t': 'fill', 'loops': [sq], 'color': rgb, 'elem': eid, 'layer': 'annotation_fill'})
            out.append({'t': 'line', 'pts': sq, 'style': line, 'elem': eid, 'layer': 'annotation'})
            out.append({'t': 'text', 'text': txt, 'origin': [o[0] + sw + tx, top - rh / 2 if n > 1 else top - sw / 2], 'x': [1.0, 0.0], 'size': size, 'font': font.get('name') or 'Arial',
                        'halign': 0, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
            top -= rh + gap
        return out

    def room_fill(self, eid, v, O, Mv, wc):
        """room colour fill: the room's floor outline (lowest planar face of its volume) in the colour scheme's colour for its parameter value"""
        if not hasattr(self, '_cs'): self._cs = {}
        if v['id'] not in self._cs: self._cs[v['id']] = self.color_schema(v)
        cs = self._cs[v['id']]
        if not cs: return []
        from .annot import Tags
        raw = self._tags_for_params().raw_params(eid)
        val = raw.get(cs['param'])
        hit = cs['entries'].get(val)
        if not hit: return []
        import rvt_elemmesh as E
        m = E.element_mesh(self.f.g, eid); T = np.asarray(m.get('tris') or [], float).reshape(-1, 3, 3)
        if not len(T): return []
        low = T[:, :, 2].min()
        flat = T[(np.abs(T[:, :, 2] - low) < 1e-3).all(1)]
        if not len(flat): return []
        uv = ((flat - O) @ Mv.T)[:, :, :2]
        loops = [t.tolist() + [t[0].tolist()] for t in uv]
        reg = patterns.region(loops)
        if reg is None: return []
        from shapely.ops import unary_union
        polys = unary_union([patterns.region([l]) for l in loops if patterns.region([l]) is not None])
        out = []
        for poly in getattr(polys, 'geoms', [polys]):
            if poly.geom_type != 'Polygon' or poly.is_empty: continue
            out.append({'t': 'fill', 'loops': [list(map(list, poly.exterior.coords))] + [list(map(list, r.coords)) for r in poly.interiors], 'color': hit[0], 'elem': eid, 'layer': 'room_fill'})
        return out

    def _tags_for_params(self):
        if getattr(self, '_tg', None) is None:
            from .annot import Tags
            self._tg = Tags(self)
        return self._tg

    def wall_layers(self, eid, loops, Mv, scale, res, ov, prims, st, cid=-2000011):
        if self._wall_layers(eid, loops, Mv, scale, res, ov, prims, st, cid) is not False or cid == -2000011: return
        # roofs / floors whose cut is a chevron or a stepped slab (Commercial typ. canopy: slope, flat top, slope): split at the vertices where the top boundary
        # turns and layer every piece on its own (Revit draws the layer lines in all of them)
        try:
            from shapely.geometry import Polygon, box
            pg = Polygon([q[:2] for q in loops[0]])
            if not pg.is_valid or len(loops) != 1: return
            C = np.asarray(pg.exterior.coords)[:-1]; n = len(C); xs = set()
            for i in range(n):
                a, b, c = C[i - 1], C[i], C[(i + 1) % n]
                u, w = b - a, c - b
                if abs(u[0]) < 1e-6 or abs(w[0]) < 1e-6: continue
                if abs(math.atan2(u[1], u[0]) - math.atan2(w[1], w[0])) > math.radians(5): xs.add(round(float(b[0]), 4))
            xs = sorted(xs)
            if len(xs) < 2: return
            xs = [C[:, 0].min() - 1] + xs + [C[:, 0].max() + 1]
            for x0, x1 in zip(xs[:-1], xs[1:]):
                pc = pg.intersection(box(x0, C[:, 1].min() - 1, x1, C[:, 1].max() + 1))
                for g in getattr(pc, 'geoms', [pc]):
                    if g.geom_type == 'Polygon' and g.area > 1e-6:
                        self._wall_layers(eid, [[list(q) for q in g.exterior.coords]], Mv, scale, res, ov, prims, st, cid)
        except Exception: self.stats['layer_split_error'] += 1

    def _wall_layers(self, eid, loops, Mv, scale, res, ov, prims, st, cid=-2000011):
        """compound wall cut: strips of the cut region along the wall normal, one per layer of the wall type
        (CompoundStructure m_layers: width, material; exterior first = the side the wall's orientation points to, m_isFlipped swaps it),
        hatched with the layer material's cut pattern and separated by thin lines. Only straight cut regions (rectangular loops)."""
        r = self.f.rec(eid)
        if not r: return
        slab = cid != -2000011           # floors and roofs: layers listed from the top (exterior) down
        t = self.f.rec(self.f.eid(r['fields'].get('m_WallAttributesId' if not slab else 'm_roofAttributesId' if cid == -2000035 else 'm_floorAttributesId')))
        cs = ob_(t['fields'].get('m_pCompoundStructure')) if t else None
        layers = [ob_(x) for x in (cs or {}).get('m_layers') or []]
        layers = [l for l in layers if (l.get('m_layerWidth') or 0) > 1e-6]
        if len(layers) < 2: return
        P = np.asarray([q[:2] for l in loops for q in l[:-1]], float)
        if len(P) < 4: return
        c = P.mean(0)
        # long axis = the edge direction carrying the most length (mod 180 deg): robust to notches and sloped tops, which tilt an SVD axis
        E = np.concatenate([np.diff(np.asarray([q[:2] for q in l], float), axis=0) for l in loops])
        Ln = np.linalg.norm(E, axis=1); ang = np.round(np.degrees(np.arctan2(E[:, 1], E[:, 0])) % 180.0, 1) % 180.0
        best = max(set(ang.tolist()), key=lambda a_: Ln[ang == a_].sum())
        ax = np.array([math.cos(math.radians(best)), math.sin(math.radians(best))]); nr = np.array([-ax[1], ax[0]])   # long axis, wall normal
        tot = sum(l['m_layerWidth'] for l in layers)
        d = (P - c) @ nr; lo, hi = d.min(), d.max()
        if abs((hi - lo) - tot) > 0.15 * tot + 0.02: return False       # not a plain straight cut of this wall type
        # which side is the exterior: wall orientation vs view: use the wall's world normal from its curve driver is not decoded yet;
        # layer 0 (exterior) on the side away from the building = the side with lower |view-depth| of the wall centre... fall back: +nr
        flip = bool(r['fields'].get('m_isFlipped'))
        if not slab:
            # exterior (layer 0) = left of the location line direction (Revit draws walls left to right: exterior on top), m_isFlipped = right;
            # layers run from lo to hi along nr, so layer 0 sits at lo when the exterior side points to -nr
            try:
                cd = ob_(r['fields'].get('m_pCurveDriver')) or {}
                dv = ob_(cd.get('m_pCrv'))['m_dirVec']
                dw = np.asarray(dv, float)
                if cd.get('m_flip'): dw = -dw
                ext = np.array([-dw[1], dw[0], 0.0]) * (-1.0 if flip else 1.0)
                ev_ = (Mv @ ext)[:2]
                if np.linalg.norm(ev_) > 1e-3:
                    order = layers if float(ev_ @ nr) < 0 else layers[::-1]
                    flip = None
            except Exception:
                pass
        if flip is not None: order = layers if not flip else layers[::-1]
        if slab:
            if nr[1] < 0: nr = -nr; d = (P - c) @ nr; lo, hi = d.min(), d.max()
            order = layers[::-1]                  # edges run from the bottom (lo) up, so the bottom layer first
        edges = [lo]
        for l in order: edges.append(edges[-1] + l['m_layerWidth'] * (hi - lo) / tot)
        mats = self.materials(); reg = patterns.region([l for l in loops if len(l) > 3])
        if reg is None: return
        from shapely.geometry import box, Polygon
        from shapely import affinity
        for i, l in enumerate(order):
            m = mats.get(self.f.eid(l.get('m_materialId'))) or {}
            cp = (m.get('cut_pattern') or {}); pat = self.doc['fill_patterns'].get(cp.get('id')) if cp.get('id') is not None else None
            if ov.get('cut_fg_visible') is False:        # cut pattern switched off by the view: Revit still prints the material's surface (model) pattern in the layer (Commercial typ. parapet 196813: 'Brick' courses)
                cp = (m.get('surface_pattern') or {}); pat = self.doc['fill_patterns'].get(cp.get('id')) if cp.get('id') is not None else None
            # strip polygon in (ax, nr) coordinates then back to view coordinates
            L = (P - c) @ ax; a0, a1 = L.min() - 1, L.max() + 1
            strip = Polygon([c + ax * a0 + nr * edges[i], c + ax * a1 + nr * edges[i], c + ax * a1 + nr * edges[i + 1], c + ax * a0 + nr * edges[i + 1]])
            piece = reg.intersection(strip)
            if piece.is_empty: continue
            if pat is not None and not pat.get('solid'):
                patterns.ANCHOR = (nr, float(edges[i] + (c @ nr))) if os.environ.get('RVT_PAT_ANCHOR', '1') == '1' else None
                try: hs_ = patterns.hatch(piece, pat, scale)
                finally: patterns.ANCHOR = None
                prims.append({'t': 'segs', 'segs': hs_, 'style': {'w': 0.1, 'rgb': cp.get('color') or [0, 0, 0], 'dash': None}, 'elem': eid, 'layer': 'cut_fill'})
            if i:                                                       # interface line between layers
                a = c + ax * a0 + nr * edges[i]; b = c + ax * a1 + nr * edges[i]
                seg = reg.intersection(Polygon([a - nr * 1e-4, b - nr * 1e-4, b + nr * 1e-4, a + nr * 1e-4]).buffer(1e-6))
                ln = reg.intersection(__import__('shapely.geometry', fromlist=['LineString']).LineString([tuple(a), tuple(b)]))
                gl = [g for g in getattr(ln, 'geoms', [ln]) if g.geom_type == 'LineString' and not g.is_empty]
                if gl: prims.append({'t': 'segs', 'segs': [[list(g.coords[0]), list(g.coords[-1])] for g in gl], 'style': dict(st, w=max(0.08, st['w'] * 0.35)), 'elem': eid, 'layer': 'cut'})

    def surface_hatch(self, eid, cid, uvw, frs, db, eps, scale, prims, ov):
        if ov.get('surf_fg_visible') is False: return                    # view override: surface pattern off (Residential first floor)
        mats = self.materials(); by = collections.defaultdict(list)
        n = np.cross(uvw[:, 1] - uvw[:, 0], uvw[:, 2] - uvw[:, 0])
        front = n[:, 2] > 1e-9                                           # facing the viewer (w towards the eye)
        for i in np.nonzero(front)[0]:
            rs = frs[i] if i < len(frs) else None
            try: rs = int(rs)
            except Exception: continue
            if rs in mats: by[rs].append(i)
        for mid, idx in by.items():
            sp = (mats[mid].get('surface_pattern') or {})
            pid_ = ov.get('surf_fg_pattern') if ov.get('surf_fg_pattern') not in (None, -1) else sp.get('id')
            pat = self.doc['fill_patterns'].get(pid_) if pid_ is not None else None
            if not pat or pat.get('solid'): continue
            polys = [patterns.region([uvw[i][:, :2].tolist() + [uvw[i][0, :2].tolist()]]) for i in idx]
            from shapely.ops import unary_union
            reg = unary_union([p for p in polys if p is not None and p.area > 1e-6])
            if reg.is_empty: continue
            segs = patterns.hatch(reg, pat, scale)
            if not segs or len(segs) > 80000: continue
            # depth of each hatch segment: nearest face plane under its midpoint is approximated by the buffer itself -> keep if the
            # buffer depth at the midpoint belongs to this element (|w - zb| small): sample w from the element's own triangles
            S = np.array(segs, float)                                    # (k,2,2)
            mids = S.mean(1)
            w = self._depth_at(uvw[idx], mids)
            ok = ~np.isnan(w)
            if not ok.any(): continue
            seg3 = np.concatenate([S[ok], np.repeat(w[ok][:, None, None], 2, 1)], 2)
            vis = db.visible_parts(seg3, eps * 1.5)
            col = ov.get('surf_fg_color') if isinstance(ov.get('surf_fg_color'), list) else (sp.get('color') or [0, 0, 0])
            if vis: prims.append({'t': 'segs', 'segs': [[a[:2].tolist(), b[:2].tolist()] for a, b in vis], 'style': {'w': 0.1, 'rgb': col, 'dash': None}, 'elem': eid, 'layer': 'surface_fill'})

    @staticmethod
    def _depth_at(tris, pts):
        """w of the nearest triangle covering each (u,v) point (nan when uncovered); tris (n,3,3), pts (k,2)"""
        out = np.full(len(pts), np.nan)
        for t in tris:
            a, b, c = t[0, :2], t[1, :2], t[2, :2]
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-12: continue
            lo = np.minimum(np.minimum(a, b), c); hi = np.maximum(np.maximum(a, b), c)
            m = (pts[:, 0] >= lo[0]) & (pts[:, 0] <= hi[0]) & (pts[:, 1] >= lo[1]) & (pts[:, 1] <= hi[1])
            if not m.any(): continue
            P = pts[m]
            l1 = ((b[1] - c[1]) * (P[:, 0] - c[0]) + (c[0] - b[0]) * (P[:, 1] - c[1])) / den
            l2 = ((c[1] - a[1]) * (P[:, 0] - c[0]) + (a[0] - c[0]) * (P[:, 1] - c[1])) / den
            l3 = 1 - l1 - l2
            inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
            if not inside.any(): continue
            w = l1 * t[0, 2] + l2 * t[1, 2] + l3 * t[2, 2]
            idx = np.nonzero(m)[0][inside]; wi = w[inside]
            cur = out[idx]; out[idx] = np.where(np.isnan(cur) | (wi > cur), wi, cur)
        return out

    def solid_material(self, frs):
        """most common face material of a solid: per-triangle render style ids (rvt_mesh 'frs'), a MaterialElem or a graphics style with a material"""
        if not frs: return None
        mats = self.materials(); c = collections.Counter()
        for rs in frs:
            if rs is None: continue
            try: rs = int(rs)
            except Exception: continue
            if rs >= 2 ** 31: continue
            if rs in mats: c[rs] += 1
            else:
                m = (self.doc['gstyles'].get(rs) or {}).get('material')
                if m not in (None, -1): c[m] += 1
        return c.most_common(1)[0][0] if c else None

    def type_params(self, eid):
        """paramset of the element's type (walls, floors, roofs, ceilings): {param id: value}, None if no host type"""
        r = self.f.rec(eid)
        if not r: return None
        fl = r['fields']
        tid = None
        for k in ('m_WallAttributesId', 'm_floorAttributesId', 'm_FloorAttributesId', 'm_roofAttributesId', 'm_ceilingAttributesId', 'm_typeId', 'm_symbolId'):
            if k in fl: tid = self.f.eid(fl[k]); break
        if tid in (None, -1): return None
        t = self.f.rec(tid)
        if not t: return None
        from .decode import Decoder
        return Decoder._paramset(self, t['fields'])

    E = property(lambda s: s.f.eid)

    def _tess(self, s):
        tg = _tess_fn()
        try: t = tg(s['geo'])
        except Exception: self.stats['tess_error'] += 1; return None
        tris = np.asarray(t['tris'], float).reshape(-1, 3, 3)
        if not len(tris): return tris, [], []
        tris = tris @ np.asarray(s['R'], float).T + np.asarray(s['o'], float)
        return tris, t.get('fidx'), t.get('frs')

    @staticmethod
    def _loops(segs, tol=1e-6):
        """chain cut segments into polylines (closed where possible)"""
        key = lambda p: (round(p[0] / tol), round(p[1] / tol))
        adj = collections.defaultdict(list)
        for i, (a, b) in enumerate(segs): adj[key(a)].append((i, 0)); adj[key(b)].append((i, 1))
        used = [False] * len(segs); loops = []
        for i in range(len(segs)):
            if used[i]: continue
            used[i] = True; a, b = segs[i]; line = [a.tolist(), b.tolist()]; cur = b
            for _ in range(len(segs)):
                nxt = [(j, e) for j, e in adj[key(cur)] if not used[j]]
                if not nxt: break
                j, e = nxt[0]; used[j] = True
                cur = segs[j][1 - e]; line.append(cur.tolist())
            loops.append(line)
        return loops


def _arc3(a, b, c, n=24):
    """points of the circle arc a -> c through b (None when collinear)"""
    ax, ay = a; bx, by = b; cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12: return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    ctr = np.array([ux, uy]); r = np.linalg.norm(a - ctr)
    th = [math.atan2(*(q - ctr)[::-1]) for q in (a, b, c)]
    t0, t1, t2 = th
    d1 = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi        # signed sweep a -> b
    d2 = (t2 - t1 + math.pi) % (2 * math.pi) - math.pi
    if d1 * d2 < 0: return None
    tot = d1 + d2
    return [ctr + r * np.array([math.cos(t0 + tot * k / n), math.sin(t0 + tot * k / n)]) for k in range(n + 1)]


def _hang(prims):
    """marker heads hang outside the crop region: they stay part of the exported picture (like datum heads)"""
    for p in prims: p['hang'] = True
    return prims
