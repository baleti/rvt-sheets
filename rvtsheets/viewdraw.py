"""Stage 3/4: draw the model content of a plan / section / elevation view as 2D primitives in VIEW coordinates
(u, v = model feet along the view's right / up vectors from the view origin).
Pipeline per element: visibility -> saved graphics walked for this view (scene.Walker) -> solids tessellated (reader rvt_mesh) ->
clipped to the view depth range -> cut regions at the cut plane + projected feature edges with hidden-line removal (hlr.DepthBuffer)
-> symbolic 2D curves projected -> styles resolved (style.Resolver)."""
import math, collections, time, os, sys
import numpy as np
from .reader import INVALID, ob as ob_, path
IN = 1 / 12.0
from .scene import Walker, ViewCtx
from .hlr import DepthBuffer
from .style import Resolver
from .visibility import Visibility
from . import patterns
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
    key = lambda p: tuple(np.round(p, 6))
    E = {}
    for i, t in enumerate(T):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ka, kb = key(t[a]), key(t[b])
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


def _font(name, bold):
    k = (name, bold)
    if k not in _FONTS:
        f = None
        try:
            import subprocess
            from PIL import ImageFont
            path = subprocess.run(['fc-match', '-f', '%{file}', '%s:%s' % (name, 'bold' if bold else 'regular')], capture_output=True, text=True, timeout=5).stdout
            f = ImageFont.truetype(path, 200)
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


ANNO_FILTER_CLASSES = ('Section', 'LinearDimString', 'SpotElevation', 'InteriorElev', 'IndependentTag', 'RoomTag', 'SpaceTag', 'AreaTag')


class ViewDrawer:
    def __init__(self, dec, doc, vis=None):
        self.dec = dec; self.doc = doc; self.f = dec.f
        self.vis = vis or Visibility(dec, doc)
        self.stats = collections.Counter()
        from .filters import FilterEval
        self.fe = FilterEval(dec, doc)

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
        try: return self._draw(vid, *a, **k)
        finally: patterns.CLIP = None

    def _draw(self, vid, px_mm=0.25, max_elems=None, skip_classes=(), skip_cats=()):
        t0 = time.time()
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
        prims = []; solids = []      # per element: (eid, cat, tris_uvw, gs)
        topo = []                    # topography surfaces (meshes, no solids): poche in sections
        occluders = []               # bodies that only hide (internal graphics styles), view coordinates
        datum_ids = []
        for k, eid in enumerate(elems):
            if max_elems and k >= max_elems: break
            info = self.vis.info.info[eid]
            if info['cls'] in skip_classes or info['cat'] in skip_cats: continue
            if ev.get('filters') and info['cls'] in ANNO_FILTER_CLASSES and info['cat'] != INVALID:
                # view filters hide annotation elements too (Snowdon L2: 'Views - Sheets' = NOT Family and Type contains '_Working' hides every section marker)
                fcat = info['cat']
                if info['cls'] == 'Section':      # filters see the marked view's category (Sections / Callouts), not the Viewers category of the marker
                    fcat = -2000537 if (self.f.rec(eid) or {}).get('fields', {}).get('m_sectionCreationMethod') == 202 else -2000200
                elif info['cls'] == 'InteriorElev': fcat = -2000535
                if not self.fe.view_filters(ev, eid, fcat, (self.doc['categories'].get(fcat) or {}).get('parent', INVALID))[0]:
                    self.stats['hidden_by_filter'] += 1; continue
            if v['kind'] == 'plan' and v.get('discipline') == 2 and info['cat'] == -2001320 and (v.get('range') or {}).get('cut') is not None:
                # structural plans: framing wholly above the cut plane is not drawn (Snowdon L2: beam 640539 z 13.7..18.3 vs cut 10.1, absent in Revit's sheet)
                bb_ = self.vis.info.bbox(eid)
                if bb_ is not None and bb_[0][2] > v['range']['cut'] + 0.01: self.stats['above_cut_hidden'] += 1; continue
            if info['cls'] in ('Grid', 'Level'): datum_ids.append(eid); continue
            if info['cls'] == 'LinearDimString':
                try: prims += self.ann.dimension(eid, O, Mv, scale, res); self.stats['dimensions'] += 1
                except Exception as ex: self.stats['dimension_error'] += 1
                continue
            if info['cls'] == 'SpotElevation':
                try:
                    sp = self.ann.spot_slope(eid, O, Mv, scale, res)
                    if sp: self.stats['spot_slopes'] += 1
                    else: sp = self.ann.spot_elevation(eid, O, Mv, scale, res); self.stats['spot_elevations'] += bool(sp)
                    prims += sp
                except Exception: self.stats['spot_error'] += 1
                continue
            if info['cls'] == 'InteriorElev':
                try: prims += _hang(self.markers.elevation(eid, O, Mv, scale, res)); self.stats['elevation_markers'] += 1
                except Exception as ex: self.stats['marker_error'] += 1
                continue
            if info['cls'] == 'InteriorElevArrow': continue
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
                    from .annot import section_marker
                    try:
                        sp_ = self.vis.section_plane_line(eid, v)
                        if sp_: prims += _hang(section_marker(self, eid, O, Mv, scale, res, vid, pts=sp_[0])); self.stats['section_markers'] += 1
                    except Exception: self.stats['marker_error'] += 1
                elif v.get('kind') == 'plan':
                    from .annot import section_marker
                    try: prims += _hang(section_marker(self, eid, O, Mv, scale, res, vid)); self.stats['section_markers'] += 1
                    except Exception: self.stats['marker_error'] += 1
                continue
            if info['cls'] in ('IndependentTag', 'RoomTag', 'SpaceTag', 'AreaTag'):
                try: prims += self.tags.tag(eid, O, Mv, scale, res); self.stats['tags'] += 1
                except Exception as ex: self.stats['tag_error'] += 1
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
            except Exception as ex: self.stats['walk_error'] += 1; continue
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
            for tx_ in pieces['texts']:
                q = dict(tx_); q['origin'] = ((np.asarray(q['origin'], float) - O) @ Mv.T)[:2].tolist(); q['layer'] = 'text'
                prims.append(q)
            under_occ = None
            if v['kind'] == 'plan' and v.get('range') and info['owner'] == INVALID and not is_rcp:
                rg = v['range']; zlo_ = min(x for x in (rg.get('depth'), rg.get('bottom')) if x is not None); bb_ = self.vis.info.bbox(eid)
                if bb_ is not None and rg.get('top') is not None and bb_[1][2] < zlo_ - 1e-6 and not anno:
                    under_occ = self._underlay_occluder(v, O, Mv, elems, bb_[1][2])
            for c in pieces['curves']:
                if not self.drawable_gs(c.get('gs')): continue
                if self._gs_hidden(ev, c.get('gs')): self.stats['hidden_subcategory_lines'] += 1; continue
                if info['cls'] in ('SiteSurface', 'TopographySurface') and v['kind'] in ('section', '3d'): continue   # contour/surface curves are not drawn in elevations (the ground profile comes from the mesh)
                pts = (np.asarray(c['pts'], float) - O) @ Mv.T
                if cut_w is not None and not is_section and (pts[:, 2] > cut_w + 1e-6).all() and False: continue
                lay = 'symbolic'
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
                pr = {'t': 'line', 'pts': pts[:, :2].tolist(), 'style': st, 'elem': eid, 'layer': lay}
                if is_section and not anno and len(pts) > 1:
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
                        if T is not None and len(T[0]): occluders.append((T[0] - O) @ Mv.T)
                    continue
                T = self._tess(s)
                if T is None or not len(T[0]): continue
                tris, fid = T[0], T[1]
                uvw = (tris - O) @ Mv.T
                m = self.solid_material(T[2] if len(T) > 2 else None)
                ov2 = dict(ov, _mat=m) if m is not None else ov
                if v['kind'] in ('section', '3d') and len(T) > 2 and T[2] is not None: ov2 = dict(ov2, _frs=T[2])
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
            db.add(c[2])
        for T in occluders:
            if cut_w is not None: T = _clip_tris_halfspace(T, np.array([0, 0, 1.0]), cut_w)
            if wf is not None and wf > -1e8: T = _clip_tris_halfspace(T, np.array([0, 0, -1.0]), -wf)
            if len(T): db.add(T)
        caps = []
        # cut regions
        if cut_w is not None:
            for eid, cid, T2, uvw, fid, gs, ov in clipped:
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
                if cid in (-2000011, -2000032, -2000035) and closed2 and (ov.get('cut_fg_visible') is not False) and (ev.get('detail_level') or 2) != 1:
                    try: self.wall_layers(eid, closed2, Mv, scale, res, ov, prims, st, cid)
                    except Exception: self.stats['layer_error'] += 1
                prims.append(prim)
                self.stats['cut_elements'] += 1
        if cut_w is not None and topo and v["kind"] == "section":
            for eid, cid, ov in topo:
                try:
                    from .compose import crop_rect_uv
                    caps += self.topo_poche(eid, cid, ov, O, Mv, cut_w, scale, res, prims, crop_rect_uv(v))
                except Exception: self.stats['topo_error'] += 1
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
            if cid in UNOBSCURED_CATS:                 # rebar: drawn through its host (Revit 'view unobscured' in the sample views)
                vis = [(a, b) for a, b in E if np.hypot(*(b[:2] - a[:2])) > px * 0.5]
            else: vis = [(a, b) for a, b in db.visible_parts(E, eps) if np.hypot(*(b[:2] - a[:2])) > px * 0.5]      # end-on edges collapse to points
            if not vis: continue
            st = res.line(gs, cid, 'proj', eid, ov=ov)
            prims.append({'t': 'segs', 'segs': [[a[:2].tolist(), b[:2].tolist()] for a, b in vis], 'style': st, 'elem': eid, 'layer': 'projection'})
        # surface patterns of the visible faces (brick, shingles, block...): face material -> Material.surface_pattern, hatched on the
        # projected front-facing triangles, kept where the depth test says the face is visible (sample points of the hatch lines)
        if v['kind'] in ('section', '3d') and scale <= 200:
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

    PAPER_LAYERS = {'annotation', 'annotation_fill', 'text', 'datum'}

    def _finish(self, prims, O, Mv):
        """control-API keys on every prim (all optional for consumers, see CONTROL-API-ANSWERS.md): cat (category id of the owner element),
        paper (sizes are paper sizes: grow with the view scale), part (sub-part of the element: text | line | leader | arrow | witness | head | frame ...),
        anchor (world feet point the annotation sits at: its first point)"""
        info = self.vis.info.info; first = {}
        for p in prims:
            e = p.get('elem')
            if e is None: continue
            if 'cat' not in p:
                c = (info.get(e) or {}).get('cat')
                if c is not None and c != INVALID: p['cat'] = c
            p.setdefault('paper', p.get('layer') in self.PAPER_LAYERS)
            if 'part' not in p: p['part'] = 'text' if p['t'] == 'text' else 'fill' if p['t'] == 'fill' else 'line'
            if p['paper'] and e not in first:
                q = p.get('origin') if p.get('origin') is not None else (p.get('pts') or [None])[0]
                if q is not None: first[e] = q
        Mi = np.linalg.inv(Mv)
        for p in prims:
            q = first.get(p.get('elem'))
            if q is not None and p['paper']:
                p['anchor'] = (np.asarray([q[0], q[1], 0.0], float) @ Mi.T + O).tolist()
        return prims

    def text_note_leaders(self, eid, O, Mv, scale, res, cat):
        """text note leaders: anchor -> elbow -> end (polyline) or, with m_bArcLeaders, the circle arc through the three points; arrow head
        of the text type's leader style (Arrow 30 Degree: full angle in param -4293960870.., size on paper) at the end"""
        r = self.f.rec(eid, 'TextNote'); fl = r['fields']
        leaders = fl.get('m_leaders') or []
        if not leaders: return []
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
        out = []
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

    def cut_fill(self, eid, cid, gs, ov, detail):
        """cut pattern of an element: override > coarse fill of the type (coarse detail, host objects) > material of the cut body > category material"""
        if ov.get('cut_fg_visible') is False: return None
        if ov.get('cut_fg_pattern') is not None: return {'pattern': ov['cut_fg_pattern'], 'color': ov.get('cut_fg_color') or [0, 0, 0]}
        info = self.vis.info.info.get(eid) or {}
        if detail == 1 and cid in self.HOST_CATS:            # coarse: host objects show their type's coarse fill (or nothing); families keep material patterns
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
        if v['kind'] != 'plan': return []
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
        if abs((hi - lo) - tot) > 0.15 * tot + 0.02: return             # not a plain straight cut of this wall type
        # which side is the exterior: wall orientation vs view: use the wall's world normal from its curve driver is not decoded yet;
        # layer 0 (exterior) on the side away from the building = the side with lower |view-depth| of the wall centre... fall back: +nr
        flip = bool(r['fields'].get('m_isFlipped'))
        order = layers if not flip else layers[::-1]
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
            # strip polygon in (ax, nr) coordinates then back to view coordinates
            L = (P - c) @ ax; a0, a1 = L.min() - 1, L.max() + 1
            strip = Polygon([c + ax * a0 + nr * edges[i], c + ax * a1 + nr * edges[i], c + ax * a1 + nr * edges[i + 1], c + ax * a0 + nr * edges[i + 1]])
            piece = reg.intersection(strip)
            if piece.is_empty: continue
            if pat is not None and not pat.get('solid'):
                prims.append({'t': 'segs', 'segs': patterns.hatch(piece, pat, scale), 'style': {'w': 0.1, 'rgb': cp.get('color') or [0, 0, 0], 'dash': None}, 'elem': eid, 'layer': 'cut_fill'})
            if i:                                                       # interface line between layers
                a = c + ax * a0 + nr * edges[i]; b = c + ax * a1 + nr * edges[i]
                seg = reg.intersection(Polygon([a - nr * 1e-4, b - nr * 1e-4, b + nr * 1e-4, a + nr * 1e-4]).buffer(1e-6))
                ln = reg.intersection(__import__('shapely.geometry', fromlist=['LineString']).LineString([tuple(a), tuple(b)]))
                gl = [g for g in getattr(ln, 'geoms', [ln]) if g.geom_type == 'LineString' and not g.is_empty]
                if gl: prims.append({'t': 'segs', 'segs': [[list(g.coords[0]), list(g.coords[-1])] for g in gl], 'style': dict(st, w=max(0.08, st['w'] * 0.35)), 'elem': eid, 'layer': 'cut'})

    def surface_hatch(self, eid, cid, uvw, frs, db, eps, scale, prims, ov):
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
            pat = self.doc['fill_patterns'].get(sp.get('id')) if sp.get('id') is not None else None
            if not pat or pat.get('solid'): continue
            polys = [patterns.region([uvw[i][:, :2].tolist() + [uvw[i][0, :2].tolist()]]) for i in idx]
            from shapely.ops import unary_union
            reg = unary_union([p for p in polys if p is not None and p.area > 1e-6])
            if reg.is_empty: continue
            segs = patterns.hatch(reg, pat, scale)
            if not segs or len(segs) > 20000: continue
            # depth of each hatch segment: nearest face plane under its midpoint is approximated by the buffer itself -> keep if the
            # buffer depth at the midpoint belongs to this element (|w - zb| small): sample w from the element's own triangles
            S = np.array(segs, float)                                    # (k,2,2)
            mids = S.mean(1)
            w = self._depth_at(uvw[idx], mids)
            ok = ~np.isnan(w)
            if not ok.any(): continue
            seg3 = np.concatenate([S[ok], np.repeat(w[ok][:, None, None], 2, 1)], 2)
            vis = db.visible_parts(seg3, eps * 1.5)
            col = (sp.get('color') or [0, 0, 0])
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
