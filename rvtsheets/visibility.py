"""Which elements a view shows (stage 1 validation target: Revit's FilteredElementCollector(doc, viewId)).
Returns ids plus, for every element, the phase status (for phase graphic overrides) and the reason when excluded."""
import json, os
import numpy as np
from .reader import ob, path, INVALID

CAT_TYPES = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(__file__), 'data', 'category_types.json'))).items()}
NEVER_CLASSES = {'GStyleElem', 'PipeSegment', 'Alignment', 'ReferencePoint', 'FormElem', 'ProfileRefPlane'}     # styles / data / constraint elements (ProfileRefPlane: sketch planes of railings/stairs): never drawn in a view
PLAN_MARKERS = {'InteriorElev', 'InteriorElevArrow', 'Section'}
OWNED_ONLY_KINDS = {'drafting', 'anon_drafting', 'legend', 'rendering', 'schedule', 'graphical_column_schedule', 'sheet'}
MARKER_CLASSES = {'Section', 'InteriorElevArrow', 'InteriorElev', 'CalloutTag'}
DATUM_CLASSES = {'Grid', 'Level', 'RefPlane'}
SKETCH_CATS = {-2000045, -2000954}            # <Sketch> lines, railing path extension lines: visible only in sketch mode
AREA_BOUNDARY = -2000079
TYPE_FLAG = {'Annotation': 'm_annotationsExcluded', 'Model': 'm_modelsExcluded', 'AnalyticalModel': 'm_analyticalModelsExcluded'}

PHASE_IDX = {'existing': 2, 'demolished': 3, 'new': 4, 'temporary': 5}
DONT_SHOW, BY_CATEGORY, OVERRIDDEN = 0, 1, 2


class ElementInfo:
    """per element: class, category, owner view, design option, phases, world bbox, is type"""
    def __init__(self, dec):
        self.dec = dec; f = dec.f; E = f.eid
        self.info = {}
        for eid, rs in f.byid.items():
            r = rs[0]; fl = r['fields']
            h = f.eh.get(eid) or {}
            is_type = 'm_symbolInfo' in fl or r['class'].endswith(('Symbol', 'Type'))
            self.info[eid] = {'cls': r['class'], 'cat': E(h.get('m_categroryId')) if h else INVALID, 'owner': E(h.get('m_ownerViewId', fl.get('m_ownerDBViewId'))),
                              'dopt': E(h.get('m_designOptionId', fl.get('m_designOptionId'))), 'created': E(fl.get('m_createdPhaseId')), 'demolished': E(fl.get('m_demolishedPhaseId')),
                              'type': is_type, 'vflags': path(h, 'm_viewRules', 'm_nVisibleViewFlags'), 'has_header': bool(h)}
        self._bb = {}

    def bbox(self, eid):
        if eid in self._bb: return self._bb[eid]
        g = self.dec.f.g.res.get(eid)
        bb = None
        if g and g.get('bbox'): bb = np.asarray(g['bbox'], float)
        self._bb[eid] = bb
        return bb


class Visibility:
    def __init__(self, dec, doc, info=None):
        self.dec = dec; self.doc = doc; self.info = info or ElementInfo(dec)
        self.cats = doc['categories']
        ph = doc['phases']; self.phase_index = {p['id']: i for i, p in enumerate(ph)}
        self.pfilters = {p['id']: p for p in doc['phase_filters']}
        self.primary_options = self._primary_options()

    def _primary_options(self):
        out = set()
        for r in self.dec.f.recs('DesignOption'):
            fl = r['fields']
            if fl.get('m_bPrimary') or fl.get('m_isPrimary') or fl.get('m_primary'): out.add(r['id'])
        return out

    def marker_in_plan(self, eid, e, v):
        """elevation/section markers in plan views (?): an arrow/section head is drawn unless Viewer.m_viewerFlags bit 0 is set and while the
        view scale is not coarser than its view's 'Hide at scales coarser than' (param -1006613); an elevation body (InteriorElev) when any arrow is"""
        f = self.dec.f
        # view discipline (Revit per-view element lists, 2020 Residential/Commercial/rst_basic, 2024 Snowdon Structural, 2026 writer test file):
        # Coordination plans list no section/elevation markers, Structural plans no elevation markers, Architectural plans show them
        disc = v.get('discipline')
        if disc == 4095: return False
        if disc == 2 and e['cls'] in ('InteriorElev', 'InteriorElevArrow'): return False
        if e['cls'] == 'InteriorElev':
            arrows = self._arrows().get(eid, [])
            return any(self.marker_in_plan(a, self.info.info.get(a, {'cls': 'InteriorElevArrow'}), v) for a in arrows) if arrows else None
        r = f.rec(eid)
        if not r: return None
        fl = r['fields']
        # elevation arrows: flags do not decide (2026 template arrows have 0 and are listed in every architectural plan; the earlier rule
        # 'bit 1 = shown' came from structural files, explained by the discipline above). Sections: keep bit 1 (Snowdon 1/5 never listed)
        pass
        # 'show in one view only' (detail sections / callouts drawn in another view): only in their parent view
        if fl.get('m_showInOneViewOnly') and f.eid(fl.get('m_parentDBViewId')) != v.get('id'): return False
        # 'hide at scales coarser than' stored on the marker as 1/N (building section 1:48: shown in 1:48 plans, not in 1:96 ones)
        cs = fl.get('m_coarserScale')
        if cs and (v.get('scale') or 0) > round(1.0 / cs) + 1e-6: return False
        if r['class'] == 'Section' and v.get('range'):
            import numpy as np
            bs = fl.get('m_boundedSpace') or {}
            if bs.get('m_basis') and bs.get('m_boundOffset'):
                # the plan's view range [bottom, top] must meet the section's vertical extent (crop box height): exact on 2020 Residential,
                # near exact on Commercial/rst_basic (tools: out/secrows.json study); Snowdon lists its sections in one plan only (unexplained)
                o = np.asarray(bs['m_orig'], float); B = np.asarray(bs['m_basis'], float); bo = bs['m_boundOffset']
                zs = [float((o + B[0] * x + B[1] * y)[2]) for x in bo[0] for y in bo[1]]
                rg = v['range']; top = rg.get('top'); bot = rg.get('bottom')
                if top is not None and bot is not None and (top < min(zs) - 0.01 or bot > max(zs) + 0.01): return False
            # an active plan crop must contain part of the section line
            cp = (v.get('crop') or {})
            pts = fl.get('m_frontCut') or []
            if cp.get('crop_active') and cp.get('basis') and pts:
                import numpy as np
                co = np.asarray(cp['origin'], float); CB = np.asarray(cp['basis'], float); cb = cp['bounds']
                P = np.asarray(pts, float); u = (P - co) @ CB[0]; w = (P - co) @ CB[1]
                if u.max() < min(cb[0]) or u.min() > max(cb[0]) or w.max() < min(cb[1]) or w.min() > max(cb[1]): return False
        tv = self.doc['views'].get(f.eid(fl.get('m_dbViewId')))
        if tv and r['class'] != 'Section':
            lim = (tv.get('params') or {}).get('-1006613')
            if lim and (v.get('scale') or 0) > int(lim): return False
            c = tv.get('crop') or {}
            if c.get('crop_active') and c.get('basis') and v.get('range'):
                # vertical extent of the target view's crop region must reach the plan's cut plane (?)
                import numpy as np
                o = np.asarray(c['origin'], float); B = np.asarray(c['basis'], float); b = c['bounds']
                zs = [float((o + B[0] * x + B[1] * y)[2]) for x in b[0] for y in b[1]]
                cut = v['range'].get('cut')
                if cut is not None and not (min(zs) - 1e-6 <= cut <= max(zs) + 1e-6): return False
        return True

    def section_plane_line(self, eid, v):
        """world points (top, bottom) where the section/callout eid's plane meets section view v's plane, over the marker's vertical
        extent; None when the planes are parallel"""
        import numpy as np
        fl = self.dec.f.rec(eid)['fields']; bs = fl.get('m_boundedSpace') or {}
        if not bs.get('m_basis') or not bs.get('m_boundOffset'): return None
        o = np.asarray(bs['m_orig'], float); B = np.asarray(bs['m_basis'], float); bo = bs['m_boundOffset']
        O = np.asarray(v['origin'], float); Z = np.asarray(v['dir'], float)
        den = float(B[0] @ Z)
        if abs(den) < 1e-6: return None
        t = float((O - o) @ Z) / den
        return [o + B[0] * t + B[1] * max(bo[1]), o + B[0] * t + B[1] * min(bo[1])], t, bo

    def marker_in_section(self, eid, v):
        """section / callout markers in section and elevation views (2020 Residential building section vs Revit's per-view list): a callout
        (m_sectionCreationMethod 202) in its parent view only; a section shows where its plane meets this view's plane within the section's
        own horizontal extent (m_boundOffset[0]) and this view's crop, never in its own view"""
        import numpy as np
        f = self.dec.f; fl = f.rec(eid)['fields']
        if f.eid(fl.get('m_dbViewId')) == v.get('id'): return False
        if fl.get('m_sectionCreationMethod') == 202 or fl.get('m_showInOneViewOnly'):
            return f.eid(fl.get('m_parentDBViewId')) == v.get('id')
        if not (fl.get('m_viewerFlags') or 0) & 2: return False
        cs = fl.get('m_coarserScale')
        if cs and (v.get('scale') or 0) > round(1.0 / cs) + 1e-6: return False
        r = self.section_plane_line(eid, v)
        if r is None: return False
        pts, t, bo = r
        if not (min(bo[0]) - 1e-6 <= t <= max(bo[0]) + 1e-6): return False
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v)
        if cr is not None:
            O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
            uv = [((p - O) @ X, (p - O) @ Y) for p in pts]
            if not (cr[0] <= uv[0][0] <= cr[2]) or max(uv[0][1], uv[1][1]) < cr[1] or min(uv[0][1], uv[1][1]) > cr[3]: return False
        return True

    def _arrows(self):
        if getattr(self, '_arr', None) is None:
            self._arr = {}
            for r in self.dec.f.recs('InteriorElevArrow'):
                self._arr.setdefault(self.dec.f.eid(r['fields'].get('m_parentId')), []).append(r['id'])
        return self._arr

    def phase_status(self, e, view_phase):
        """-> 'existing'|'new'|'demolished'|'temporary'|'past'|'future'|None (element not phased)"""
        if view_phase in (None, INVALID) or e['created'] == INVALID: return None
        p = self.phase_index.get(view_phase); c = self.phase_index.get(e['created']); d = self.phase_index.get(e['demolished']) if e['demolished'] != INVALID else None
        if p is None or c is None: return None
        if c > p: return 'future'
        if d is not None and d < p: return 'past'
        if d is not None and d == p: return 'temporary' if c == p else 'demolished'
        return 'new' if c == p else 'existing'

    def _filter_hidden(self, v, eid, c):
        """view filters (Visibility off) that match the element: Snowdon L2's 'Views - Working' / 'Views - Sheets' hide every section/callout/elevation marker"""
        if getattr(self, '_fe', None) is None:
            from .filters import FilterEval
            self._fe = FilterEval(self.dec, self.doc)
        par = (self.cats.get(c) or {}).get('parent', INVALID)
        return not self._fe.view_filters(v, eid, c, par)[0]

    def _filter_cat(self, eid, e):
        """category filters see: the marked view's category for section/callout/elevation markers"""
        if e['cls'] == 'Section':
            r = self.dec.f.rec(eid)
            return -2000537 if r and r['fields'].get('m_sectionCreationMethod') == 202 else -2000200
        if e['cls'] == 'InteriorElev': return -2000535
        return e['cat']

    def hidden_categories(self, v):
        s = set(); flags = {}
        for df in v.get('draw_filters') or []:
            if df.get('m_categoryIds') is not None:
                s |= set(df['m_categoryIds'])
                flags = {k: df.get(k) for k in ('m_annotationsExcluded', 'm_modelsExcluded', 'm_analyticalModelsExcluded', 'm_importsExcluded')}
        return s, flags

    def effective(self, v):
        """view settings with the view template applied (template controls V/G, phase filter, detail level... when assigned): first approximation
        = take V/G (hidden categories, category overrides, filters) from the template when one is assigned"""
        t = v.get('view_template')
        tv = self.doc['views'].get(t) or self.doc['views'].get(str(t)) if t not in (None, INVALID) else None
        if not tv: return v
        w = dict(v)
        for k in ('draw_filters', 'category_overrides', 'filters', 'detail_level', 'phase_filter', 'discipline'):
            if tv.get(k) is not None: w[k] = tv[k]
        return w

    def volume(self, v):
        """view volume test on a world bbox -> callable(bb) -> bool"""
        kind = v['kind']; crop = v.get('crop') or {}
        if kind == 'plan' and v.get('range'):
            r = v['range']; zlo = min(x for x in (r.get('depth'), r.get('bottom')) if x is not None); zhi = r.get('top')
            ub = r.get('underlay_bottom'); ut = r.get('underlay_top')
            if ub is not None and ut is not None and abs(ub) < 1e8 and abs(ut) < 1e8:      # underlay range (shown halftone)
                zlo = min(zlo, ub); zhi = max(zhi, ut)
            if v.get('dir') and v['dir'][2] < 0: pass
            cut = None
            if crop.get('crop_active'):
                cut = self._crop_test(crop, use_z=False)
            def test(bb):
                if bb[1][2] < zlo - 1e-6 or bb[0][2] > zhi + 1e-6: return False
                return cut(bb) if cut else True
            return test
        sb = v.get('section_box')
        if kind == '3d' and sb and sb.get('on'):
            return self._crop_test(dict(sb), use_z=True, xy=True, z='all')
        if kind in ('section', 'plan') and crop.get('basis'):
            return self._crop_test(crop, use_z=kind == 'section', xy=crop.get('crop_active'))
        return lambda bb: True

    def _crop_test(self, crop, use_z=True, xy=True, z=True):
        """oriented box test in the crop frame: x/y = crop region (when xy), z: near plane (bounds min) always for sections, far plane (bounds max) when active"""
        o = np.asarray(crop['origin'], float); B = np.asarray(crop['basis'], float); b = crop['bounds']
        lo = np.array([b[i][1] for i in range(3)], float); hi = np.array([b[i][0] for i in range(3)], float)
        act = crop.get('active') or [[1, 1]] * 3
        use_lo = np.array([xy, xy, use_z]); use_hi = np.array([xy, xy, use_z and bool(act[2][0]) if z != 'all' else True])
        def test(bb):
            corners = np.array([[bb[i][0], bb[j][1], bb[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
            loc = (corners - o) @ B.T
            mn = loc.min(0); mx = loc.max(0)
            return bool(np.all((~use_hi | (mn <= hi + 1e-6)) & (~use_lo | (mx >= lo - 1e-6))))
        return test

    def elements(self, vid, explain=False):
        v0 = self.doc['views'].get(vid) or self.doc['views'].get(str(vid))
        v = self.effective(v0)
        hid, xflags = self.hidden_categories(v)
        hidden_el = set(v0.get('hidden_elements') or [])
        pf = self.pfilters.get(v.get('phase_filter'))
        vol = self.volume(v)
        out = {}; why = {}
        for eid, e in self.info.info.items():
            if not e['has_header'] and e['cls'] in ('Level', 'Grid') and not e['type']:
                # some datums (2020 Residential level 'first floor') have no element header: category from the class, shown by default
                e = dict(e, cat={'Level': -2000240, 'Grid': -2000220}[e['cls']], vflags=1, has_header=True)
            if e['type'] or not e['has_header']: continue
            if e['owner'] not in (INVALID, vid): continue
            if v['kind'] in OWNED_ONLY_KINDS and e['owner'] != vid: continue
            if v['kind'] == '3d' and e['cls'] in MARKER_CLASSES: why[eid] = 'marker_in_3d'; continue
            if e['cls'] == 'ModelClipBox' and (v.get('section_box') or {}).get('id') != eid: why[eid] = 'other_views_section_box'; continue
            if e['cls'] in NEVER_CLASSES: why[eid] = 'never_drawn_class'; continue
            if e['cls'] in ('Viewport', 'GCSViewport') and e['owner'] != vid: why[eid] = 'viewport_not_on_this_sheet'; continue
            if e['cat'] in SKETCH_CATS: why[eid] = 'sketch_line'; continue
            if e['cat'] == AREA_BOUNDARY and v.get('class') != 'DBViewPlan' or (e['cat'] == AREA_BOUNDARY and (v.get('range') or {}).get('plan_view_type') != 4): why[eid] = 'area_boundary_outside_area_plan'; continue
            if e['cls'] == 'Level' and v['kind'] in ('plan', '3d'): why[eid] = 'level_in_plan_or_3d'; continue
            if e['cls'] in ('Grid', 'RefPlane') and v['kind'] == '3d': why[eid] = 'datum_in_3d'; continue
            if eid in hidden_el: why[eid] = 'hidden_element'; continue
            c = e['cat']
            if v.get('filters') and (e['cls'] in ('Section', 'InteriorElev') or c != INVALID) and self._filter_hidden(v, eid, self._filter_cat(eid, e)):
                why[eid] = 'filter_hidden'; continue
            if v['kind'] == 'plan' and e['cls'] in PLAN_MARKERS:
                ok = self.marker_in_plan(eid, e, v)
                if ok is not None:
                    if ok and c not in hid: out[eid] = None
                    else: why[eid] = 'marker_rule'
                    continue
            if v['kind'] == 'section' and e['cls'] == 'Section':
                ok = self.marker_in_section(eid, v)
                if ok and c not in hid: out[eid] = None
                else: why[eid] = 'marker_rule'
                continue
            if c == INVALID: why[eid] = 'no_category'; continue
            if not (e['vflags'] or 0) & 1: why[eid] = 'view_flags'; continue
            par = (self.cats.get(c) or {}).get('parent', INVALID)
            ct = CAT_TYPES.get(c) or CAT_TYPES.get(par)
            if ct == 'Internal' or (ct in TYPE_FLAG and xflags.get(TYPE_FLAG[ct])): why[eid] = 'category_type_' + str(ct); continue
            if c in hid or par in hid: why[eid] = 'category_hidden'; continue
            st = self.phase_status(e, v.get('phase'))
            if st in ('past', 'future'): why[eid] = 'phase_' + st; continue
            if st and pf and pf.get('presentation'):
                if pf['presentation'][PHASE_IDX[st]] == DONT_SHOW: why[eid] = 'phase_filter_' + st; continue
            if e['dopt'] not in (INVALID,) and e['dopt'] != -4 and self.primary_options and e['dopt'] not in self.primary_options: why[eid] = 'design_option'; continue
            if e['owner'] == INVALID:
                bb = self.info.bbox(eid)
                if bb is not None and not vol(bb): why[eid] = 'outside_view_volume'; continue
                if bb is None and e['cls'] not in DATUM_CLASSES and e['cls'] not in ('Viewer3d', 'ExtentElem', 'ModelClipBox'): why[eid] = 'no_graphics_no_bbox'; continue
            out[eid] = st
        return (out, why) if explain else out
