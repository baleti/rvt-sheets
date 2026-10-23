import os
"""Which elements a view shows (stage 1 validation target: Revit's FilteredElementCollector(doc, viewId)).
Returns ids plus, for every element, the phase status (for phase graphic overrides) and the reason when excluded."""
import json, os
import numpy as np
from .reader import ob, path, INVALID, wref
from .viewrules import property_line_candidate

CAT_TYPES = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(__file__), 'data', 'category_types.json'))).items()}
NEVER_CLASSES = {'GStyleElem', 'PipeSegment', 'Alignment', 'ReferencePoint', 'FormElem', 'ProfileRefPlane'}     # styles / data / constraint elements (ProfileRefPlane: sketch planes of railings/stairs): never drawn in a view
NOT_IN_3D = {'BasePoint', 'CoordinateSystemDisplayElem', 'CurveElem'}      # project base / survey point, coordinate display and these curves are in no Snowdon 3D list (0 of 13 views, Revit 2024)
PLAN_MARKERS = {'InteriorElev', 'InteriorElevArrow', 'Section'}
OWNED_ONLY_KINDS = {'drafting', 'anon_drafting', 'legend', 'rendering', 'schedule', 'graphical_column_schedule', 'sheet'}
MARKER_CLASSES = {'Section', 'InteriorElevArrow', 'InteriorElev', 'CalloutTag'}
ABOVE_CUT_KEEP = {'Viewer3d', 'JoistSystem', 'BeamSystem', 'Rebar', 'RebarInSystem', 'AreaReinforcement', 'PathReinforcement', 'PropertyLineSegment', 'Property', 'Grid', 'Level', 'RefPlane', 'InteriorElev', 'InteriorElevArrow', 'Section', 'ExtentElem', 'ModelClipBox'}
ABOVE_CUT_KEEP_CATS = {-2000151, -2001330, -2001320, -2001300}      # generic models (Residential), structural columns / framing / foundations (Snowdon structural plans list members above the cut)
DATUM_CLASSES = {'Grid', 'Level', 'RefPlane'}
SKETCH_CATS = {-2000045, -2000954}            # <Sketch> lines, railing path extension lines: visible only in sketch mode
AREA_BOUNDARY = -2000079
TYPE_FLAG = {'Annotation': 'm_annotationsExcluded', 'Model': 'm_modelsExcluded', 'AnalyticalModel': 'm_analyticalModelsExcluded'}

TOUCH = float(os.environ.get('RVT_TOUCH', '-1e-6'))
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
            is_type = 'm_symbolInfo' in fl or (r['class'].endswith(('Symbol', 'Type')) and r['class'] != 'SpanDirectionSymbol')       # SpanDirectionSymbol is an instance (floor span annotation)
            self.info[eid] = {'cls': r['class'], 'cat': E(h.get('m_categroryId')) if h else INVALID, 'owner': E(h.get('m_ownerViewId', fl.get('m_ownerDBViewId'))),
                              'dopt': E(h.get('m_designOptionId', fl.get('m_designOptionId'))), 'rphase': E(fl.get('m_phaseId')) if r['class'] == 'RoomElem' and E(fl.get('m_areaSchemeId')) in (INVALID, None, -1) else INVALID, 'created': E(fl.get('m_createdPhaseId')), 'demolished': E(fl.get('m_demolishedPhaseId')),
                              'fam': E(fl.get('m_famId')) if r['class'] == 'SWall' else INVALID, 'type': is_type, 'vflags': path(h, 'm_viewRules', 'm_nVisibleViewFlags'), 'has_header': bool(h)}
        self._bb = {}

    def bbox(self, eid):
        if eid in self._bb: return self._bb[eid]
        g = self.dec.f.g.res.get(eid)
        bb = None
        if g and g.get('bbox'): bb = np.asarray(g['bbox'], float)
        self._bb[eid] = bb
        return bb


ABOVE_CUT_CATS = ({-2000011} if os.environ.get('RVT_WALL_ABOVE', '1') == '1' else set()) | {-2001320, -2001330, -2009000, -2001300, -2009030, -2000032}


class Visibility:
    def __init__(self, dec, doc, info=None):
        self.dec = dec; self.doc = doc; self.info = info or ElementInfo(dec)
        self.cats = doc['categories']
        ph = doc['phases']; self.phase_index = {p['id']: i for i, p in enumerate(ph)}
        self.pfilters = {p['id']: p for p in doc['phase_filters']}
        self.primary_options = self._primary_options()
        self.option_set = {r['id']: self.dec.f.eid(r['fields'].get('m_DesignOptionSetId')) for r in self.dec.f.recs('DesignOption')}

    def shown_options(self, v):
        """design options visible in view v: the primary option of every set, replaced by the view's own choice per set (View > Design Options)"""
        chosen = set(self.primary_options)
        for st, opt in v.get('design_options') or []:
            chosen = {o for o in chosen if self.option_set.get(o) != st}
            if opt not in (None, INVALID): chosen.add(opt)
        return chosen

    def _primary_options(self):
        out = set()
        for r in self.dec.f.recs('DesignOptionSet'):             # DesignOptionSet.m_mainDesignOption = the primary option (2020 rst_basic: option 1)
            m = self.dec.f.eid(r['fields'].get('m_mainDesignOption'))
            if m not in (None, INVALID): out.add(m)
        for r in self.dec.f.recs('DesignOption'):
            fl = r['fields']
            if fl.get('m_bPrimary') or fl.get('m_isPrimary') or fl.get('m_primary'): out.add(r['id'])
        return out

    def marker_in_plan(self, eid, e, v):
        """elevation/section markers in plan views (?): an arrow/section head is drawn unless Viewer.m_viewerFlags bit 0 is set and while the
        view scale is not coarser than its view's 'Hide at scales coarser than' (param -1006613); an elevation body (InteriorElev) when any arrow is"""
        import numpy as np
        f = self.dec.f
        # view discipline (Revit per-view element lists, 2020 Residential/Commercial/rst_basic, 2024 Snowdon Structural, 2026 writer test file):
        # Coordination plans list no section/elevation markers, Structural plans no elevation markers, Architectural plans show them
        disc = v.get('discipline')
        if disc == 4095 and e['cls'] in ('InteriorElev', 'InteriorElevArrow') and os.environ.get('RVT_MARKER_DISC', '1') == '1': return False      # coordination plans list no elevation markers; sections do show (2026 rosette 'VR plan') when no filter hides them
        if disc == 2 and e['cls'] in ('InteriorElev', 'InteriorElevArrow') and os.environ.get('RVT_MARKER_DISC', '1') == '1': return False
        if e['cls'] == 'InteriorElev':
            cp_ = v.get('crop') or {}
            if cp_.get('crop_active') and cp_.get('basis') and os.environ.get('RVT_MARKER_CROP', '1') == '1':
                pos_ = (f.rec(eid) or {'fields': {}})['fields'].get('m_pos')          # a marker outside an active plan crop is not listed (2024 rosetta markers scene: dependent view cropped to one text note)
                if pos_:
                    co_ = np.asarray(cp_['origin'], float); CB_ = np.asarray(cp_['basis'], float); bb_ = cp_['bounds']; q_ = (np.asarray(pos_, float) - co_) @ CB_.T
                    if not (min(bb_[0]) - 0.5 <= q_[0] <= max(bb_[0]) + 0.5 and min(bb_[1]) - 0.5 <= q_[1] <= max(bb_[1]) + 0.5): return False
            arrows = self._arrows().get(eid, [])
            return any(self.marker_in_plan(a, self.info.info.get(a, {'cls': 'InteriorElevArrow'}), v) for a in arrows) if arrows else None
        r = f.rec(eid)
        if not r: return None
        fl = r['fields']
        # elevation arrows: flags do not decide (2026 template arrows have 0 and are listed in every architectural plan; the earlier rule
        # 'bit 1 = shown' came from structural files, explained by the discipline above). Sections: keep bit 1 (Snowdon 1/5 never listed)
        pass
        # an elevation marker belongs to the phase of the view it was created in = the phase of its elevation view: other-phase plans do not list it (2024 rosetta markers scene:
        # 'create' plan phase 7019 lists the marker, its duplicates of phase 64113 do not)
        if r['class'] == 'InteriorElevArrow':
            cp_ = v.get('crop') or {}; par_ = f.eid(fl.get('m_parentId'))
            if cp_.get('crop_active') and cp_.get('basis') and par_ not in (None, INVALID) and os.environ.get('RVT_MARKER_CROP', '1') == '1':
                pos_ = (f.rec(par_) or {'fields': {}})['fields'].get('m_pos')
                if pos_:
                    co_ = np.asarray(cp_['origin'], float); CB_ = np.asarray(cp_['basis'], float); bb_ = cp_['bounds']; q_ = (np.asarray(pos_, float) - co_) @ CB_.T
                    if not (min(bb_[0]) - 0.5 <= q_[0] <= max(bb_[0]) + 0.5 and min(bb_[1]) - 0.5 <= q_[1] <= max(bb_[1]) + 0.5): return False
        if r['class'] == 'InteriorElevArrow' and os.environ.get('RVT_ARROW_PHASE', '1') == '1':
            tv_ = self.doc['views'].get(f.eid(fl.get('m_dbViewId')))
            if tv_ and tv_.get('phase') not in (None, INVALID, -1) and v.get('phase') not in (None, INVALID, -1) and tv_['phase'] != v['phase']: return False
        # 'show in one view only' (detail sections / callouts drawn in another view): only in their parent view
        if fl.get('m_showInOneViewOnly') and f.eid(fl.get('m_parentDBViewId')) != v.get('id'): return False
        # 'hide at scales coarser than' stored on the marker as 1/N (building section 1:48: shown in 1:48 plans, not in 1:96 ones)
        cs = fl.get('m_coarserScale')
        if cs and (v.get('scale') or 0) > round(1.0 / cs) + 1e-6: return False
        if r['class'] == 'Section' and v.get('kind') == 'plan' and (fl.get('m_viewerFlags') or 0) & 7 == 7 and disc != 4095 and os.environ.get('RVT_SECFLAG7', '0') == '1':
            return False         # viewer flags 7 sections: only coordination plans ('VR plan') list their marker; the 2026 rosetta 'Level 2' floor plan and ceiling plan (cut inside the extent) hide it
        if r['class'] == 'Section' and v.get('range'):
            import numpy as np
            bs = fl.get('m_boundedSpace') or {}
            if bs.get('m_basis') and bs.get('m_boundOffset'):
                # the plan's view range [bottom, top] must meet the section's vertical extent (crop box height): exact on 2020 Residential,
                # near exact on Commercial/rst_basic (tools: out/secrows.json study); Snowdon lists its sections in one plan only (unexplained)
                o = np.asarray(bs['m_orig'], float); B = np.asarray(bs['m_basis'], float); bo = bs['m_boundOffset']
                zs = [float((o + B[0] * x + B[1] * y)[2]) for x in bo[0] for y in bo[1]]
                rg = v['range']; top = rg.get('top'); bot = rg.get('bottom')
                if os.environ.get('RVT_SECCUT', '1') == '1' and rg.get('cut') is not None and rg.get('plan_view_type') != 2:
                    if not (min(zs) - 0.01 <= rg['cut'] <= max(zs) + 0.01): return False          # the plan's CUT plane must lie in the section's vertical extent (2026 rosetta: 'Level 2' cut 17.1 / 'Site' cut 32.8 against 18..30 hide the marker, 'VR plan' cut 24 shows it)
                elif top is not None and bot is not None and (top < min(zs) - 0.01 or bot > max(zs) + 0.01): return False
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
        fc = [np.asarray(q, float) for q in (fl.get('m_frontCut') or [])]
        if len(fc) > 2:
            # jogged section: the marker sits on the straight piece (parallel to the section's right axis) nearest to where the view plane meets it
            # (Residential 'Building Section' seen from the east: Revit puts the A-2 head on the last piece, 12 ft from the first)
            best = None
            for a, b in zip(fc[:-1], fc[1:]):
                dv = b - a
                if np.linalg.norm(dv) < 1e-6 or abs(float(dv @ B[0])) < 0.98 * np.linalg.norm(dv): continue
                base = o + B[2] * float((a - o) @ B[2])
                tb = float((O - base) @ Z) / den
                lo, hi = sorted((float((a - o) @ B[0]), float((b - o) @ B[0])))
                tt = float(tb)
                dist = max(lo - tt, tt - hi, 0.0)
                if best is None or dist < best[0] - 1e-9: best = (dist, base, tb)
            if best is not None: o, t = best[1], best[2]
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
        if ((fl.get('m_viewerFlags') or 0) & 7) == 7: return False      # flags 7 (Snowdon: 0 of 27 listings in other section views); 1 and 5 do appear, 3 appears in the 2020 samples
        cs = fl.get('m_coarserScale')
        if cs and (v.get('scale') or 0) > round(1.0 / cs) + 1e-6: return False
        r = self.section_plane_line(eid, v)
        if r is None: return False
        pts, t, bo = r
        tol = float(os.environ.get('RVT_SECTION_TOL', '9.5'))       # the plane may miss the section's own extent by up to ~8.3 ft and still list the marker (Residential A-2 in east/west: 8.3 ft out, Snowdon Longitudinal marker in 'Longitudinal': 8.3 ft out) but not by 10.9 ft (Snowdon Sawtooth in Cross Section) nor by 100+ ft (Snowdon elevations)
        if not (min(bo[0]) - tol <= t <= max(bo[0]) + tol): return False      # elevations list every section line crossing their plane (2020 Residential east/north/south)
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v)
        if cr is not None:
            O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
            uv = [((p - O) @ X, (p - O) @ Y) for p in pts]
            if not (cr[0] <= uv[0][0] <= cr[2]) or max(uv[0][1], uv[1][1]) < cr[1] or min(uv[0][1], uv[1][1]) > cr[3]: return False
        return True

    def _elevation_views(self):
        if getattr(self, '_ev', None) is None:
            self._ev = {self.dec.f.eid(r['fields'].get('m_dbViewId')) for r in self.dec.f.recs('InteriorElevArrow')}
        return self._ev

    def _link_visible(self, eid, vid):
        """a link instance without a bounding box (nothing loaded to measure) is still in the view's list while its link type is visible in the view (2024 vg_links scene); Snowdon: only where the link is not hidden per view"""
        try:
            from .vg.links import view_links, link_instances
            c = self.__dict__.setdefault('_lv', {})
            if vid not in c: c[vid] = view_links(self.dec.f, self.dec.f.rec(vid)['fields'])
            sym = (link_instances(self.dec.f).get(eid) or {}).get('symbol')
            if (self.dec.f.rec(sym) or {'fields': {}})['fields'].get('m_relative'): return False       # relative-path links (every Snowdon link) are not loaded: Revit lists none of their instances; the oracle scene's absolute-path links are listed
            return bool((c[vid].get(sym) or {}).get('visible', False))
        except Exception: return False

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

    def _template_keys(self, tv):
        """view settings taken from the template: only the groups it controls (TPLCTL; a parameter excluded from the template keeps the view's own value)"""
        from .vg import template as T
        ks = []
        if all(T.controls(tv, g) for g in ('model', 'annotation', 'analytical', 'import')): ks += ['draw_filters', 'category_overrides']       # the exclusion set and the overrides mix all four tabs: copied only when the template controls all of them
        for g, keys in (('filters', ('filters',)), ('detail_level', ('detail_level',)), ('phase_filter', ('phase_filter',)), ('discipline', ('discipline',))):
            if T.controls(tv, g): ks += [k for k in keys if k not in ks]
        return ks

    def _nobox_room_plans(self, level):
        """ids of the uncropped, non-ceiling plans whose primary level is `level` (candidates for listing a room without extent)"""
        c = getattr(self, '_nbp', None)
        if c is None: c = self._nbp = {}
        if level not in c:
            c[level] = sorted(k for k, w in self.doc['views'].items() if w.get('kind') == 'plan' and not w.get('template') and (w.get('range') or {}).get('plan_view_type') == 1
                              and not (w.get('crop') or {}).get('crop_active') and ((w.get('range') or {}).get('levels') or [None])[0] == level and w.get('class', 'DBViewPlan') == 'DBViewPlan')
        return c[level]

    def effective(self, v):
        """view settings with the view template applied (template controls V/G, phase filter, detail level... when assigned): first approximation
        = take V/G (hidden categories, category overrides, filters) from the template when one is assigned"""
        t = v.get('view_template')
        tv = self.doc['views'].get(t) or self.doc['views'].get(str(t)) if t not in (None, INVALID) else None
        if not tv: return v
        w = dict(v)
        for k in self._template_keys(tv):
            if tv.get(k) is not None: w[k] = tv[k]
        return w

    def volume(self, v):
        """view volume test on a world bbox -> callable(bb) -> bool"""
        kind = v['kind']; crop = v.get('crop') or {}
        if kind == 'plan' and v.get('range'):
            r = v['range']; zlo = min(x for x in (r.get('depth'), r.get('bottom')) if x is not None); zhi = r.get('top')
            if r.get('plan_view_type') == 2 and r.get('cut') is not None and os.environ.get('RVT_CEILING_RANGE', '1') == '1': zlo = r['cut']       # reflected ceiling plans look up: elements from the cut plane to the top (Residential 'attic' ceiling plan 9952 lists 0 of the 15 predicted walls below its cut)
            rcp_strict = r.get('plan_view_type') == 2 and os.environ.get('RVT_RCP_TOUCH', '1') == '1' and v.get('discipline') != 2      # ceiling plans: floors / stair runs whose top only touches the range bottom are unlisted (Residential RCP 36 / attic: 6 floors + 4 runs)
            ub = r.get('underlay_bottom'); ut = r.get('underlay_top')
            if ub is not None and ut is not None and abs(ub) < 1e8 and abs(ut) < 1e8:      # underlay range (shown halftone)
                zlo = min(zlo, ub); zhi = max(zhi, ut)
            if v.get('dir') and v['dir'][2] < 0: pass
            cut = None
            if crop.get('crop_active'):
                cut = self._crop_test(crop, use_z=False)
            def test(bb):
                if bb[1][2] < zlo + (1e-6 if rcp_strict and bb[1][2] - bb[0][2] > 1e-3 else TOUCH) or bb[0][2] > zhi + 1e-6: return False         # an element whose top only touches the bottom of the range (floors on the level below, stair runs ending at the level) is outside it
                return cut(bb) if cut else True
            return test
        sb = v.get('section_box')
        if kind == '3d' and sb and sb.get('on'):
            return self._crop_test(dict(sb), use_z=True, xy=True, z='all')
        if kind in ('section', 'plan') and crop.get('basis'):
            near = None
            cu = (v.get('cutters') or {}).get('Cutter')
            if kind == 'section' and cu and cu.get('origin') is not None and os.environ.get('RVT_CUTTER', '1') == '1':
                near = float((np.asarray(cu['origin'], float) - np.asarray(crop['origin'], float)) @ np.asarray(crop['basis'][2], float))       # the view's own cut plane (callouts of a jogged section sit on different pieces)
            if kind == 'section' and not cu and v.get('class') == 'DBViewSection' and os.environ.get('RVT_JOG', '1') == '1':
                pcs = self._jog_pieces(v, crop)
                if pcs:
                    nmin = min(nz for nz, _ in pcs)
                    tests = [self._crop_test(crop, use_z=True, xy=crop.get('crop_active'), near=nz, xr=xr) for nz, xr in pcs]
                    loose = [self._crop_test(crop, use_z=True, xy=crop.get('crop_active'), near=nmin, xr=xr) for nz, xr in pcs]
                    self._loose_vol = lambda bb: any(t(bb) for t in loose)      # stairs of a jogged section are listed down to the crop's near clip, not only behind their piece's cut plane
                    return lambda bb: any(t(bb) for t in tests)
            return self._crop_test(crop, use_z=kind == 'section', xy=crop.get('crop_active'), near0=kind == 'section' and near is None and v.get('id') not in self._callout_views(), near=near)
        return lambda bb: True

    def _origin_in_view(self, v, vol):
        """the coordinate-system display element is listed only in views whose volume contains the model origin: plans by their PRIMARY range (no underlay) and crop, sections / 3D by the view volume
        (Residential: unlisted in the basement / attic / ceiling plans, the boxed {3D} view and the 'typ. door head' section)"""
        z = np.zeros((2, 3))
        if v['kind'] == 'plan' and v.get('range'):
            r = v['range']; zs = [x for x in (r.get('bottom'), r.get('depth')) if x is not None]
            zlo = r['cut'] if r.get('plan_view_type') == 2 and r.get('cut') is not None else (min(zs) if zs else -1e9)
            if not (zlo - 1e-6 <= 0.0 <= (r.get('top') if r.get('top') is not None else 1e9) + 1e-6): return False
            from .compose import crop_rect_uv
            cr = crop_rect_uv(v)
            if cr is not None:
                O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
                u, w = float((-O) @ X), float((-O) @ Y)
                return cr[0] <= u <= cr[2] and cr[1] <= w <= cr[3]
            return True
        if v['kind'] == 'section' and (v.get('crop') or {}).get('basis'):
            # sections / elevations: only the depth matters, not the crop frame: listed iff the origin lies beyond the crop frame's cut plane (z > 0 in the crop basis: Commercial 12 of 12,
            # rst_basic 12 of 12 views; typ. wall / window / building section of Residential with z -1.7 are the exceptions, the door head with the same z is unlisted)
            c = v['crop']; l = (np.zeros(3) - np.asarray(c['origin'], float)) @ np.asarray(c['basis'], float).T
            return bool(l[2] > 0.01)
        return bool(vol(z))

    def _camera_disc(self, eid):
        """discipline of the 3D view a camera (Viewer3d) belongs to"""
        m = self.__dict__.get('_cam_disc')
        if m is None:
            m = self._cam_disc = {}
            for vid, vv in self.doc['views'].items():
                if vv.get('kind') == '3d':
                    try: m[self.dec.f.eid(self.dec.f.rec(vid)['fields']['m_viewerId'])] = vv.get('discipline')
                    except Exception: pass
        return m.get(eid)

    def _room_on_cut_line(self, eid, v):
        """does the section line (straight, or jogged: viewer m_frontCut pieces, or the callout's own cutter) cross the room's bbox"""
        bb = self.info.bbox(eid)
        if bb is None or not np.all(bb[0] <= bb[1]) or np.abs(bb).max() > 1e20: return True
        crop = v['crop']; co = np.asarray(crop['origin'], float); B = np.asarray(crop['basis'], float); b = crop['bounds']
        pts = np.array([[x, y, z] for x in (bb[0][0], bb[1][0]) for y in (bb[0][1], bb[1][1]) for z in (bb[0][2], bb[1][2])])
        loc = (pts - co) @ B.T; x0, x1, z0, z1 = loc[:, 0].min(), loc[:, 0].max(), loc[:, 2].min(), loc[:, 2].max()
        cu = (v.get('cutters') or {}).get('Cutter')
        pcs = None
        if cu and cu.get('origin') is not None: pcs = [(float((np.asarray(cu['origin'], float) - co) @ B[2]), (-1e9, 1e9))]
        elif v.get('class') == 'DBViewSection' and os.environ.get('RVT_JOG', '1') == '1': pcs = self._jog_pieces(v, crop)
        if not pcs: pcs = [(float(b[2][1]), (-1e9, 1e9))]
        tol = 0.05
        return any(x1 >= xr[0] - tol and x0 <= xr[1] + tol and z0 - tol <= nz <= z1 + tol for nz, xr in pcs)

    def _datum_perpendicular(self, eid, v):
        """sections / elevations list only datum planes perpendicular to the view plane (|n.dir| <= 0.05; Snowdon 7.5 degree grid, rst_basic angled section 'Section Wall2': 21 reference planes + 16 grids unlisted)"""
        r = self.dec.f.rec(eid)
        srf = ob((r or {}).get('fields', {}).get('m_pSurface')) or {}
        if not srf.get('m_xVec') or not srf.get('m_yVec'): return True
        n = np.cross(np.asarray(srf['m_xVec'], float), np.asarray(srf['m_yVec'], float)); Z = np.asarray(v['dir'], float)
        nn = np.linalg.norm(n) * np.linalg.norm(Z)
        return nn < 1e-9 or abs(float(n @ Z)) / nn <= 0.05

    def _datum_meets_crop(self, eid, v):
        """a grid / reference plane in a section with an active crop is listed only where its (finite) plane meets the view plane inside the crop rectangle
        (Commercial detail 'Typ. Canopy/Flat Roof' 1:8: 52 reference planes + 11 grids predicted, none in Revit's list)"""
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v)
        if cr is None or os.environ.get('RVT_DATUM_CROP', '1') != '1': return True
        r = self.dec.f.rec(eid); srf = ob((r or {}).get('fields', {}).get('m_pSurface')) or {}
        env = path(srf, 'm_Envelope', 'm_corners')
        if not (srf.get('m_origin') and srf.get('m_xVec') and env): return True
        o = np.asarray(srf['m_origin'], float); x = np.asarray(srf['m_xVec'], float); y = np.asarray(srf['m_yVec'], float)
        O = np.asarray(v['origin'], float); Z = np.asarray(v['dir'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
        (a0, b0), (a1, b1) = env
        c = [o + x * a0 + y * b0, o + x * a1 + y * b0, o + x * a1 + y * b1, o + x * a0 + y * b1]
        pts = c                                        # perpendicular planes project onto the view plane: a line (end-on when it runs along the view direction), in front or behind
        uv = np.array([[(q - O) @ X, (q - O) @ Y] for q in pts]); tol = 0.25
        return bool(uv[:, 0].max() >= cr[0] - tol and uv[:, 0].min() <= cr[2] + tol and uv[:, 1].max() >= cr[1] - tol and uv[:, 1].min() <= cr[3] + tol)

    def _is22(self):
        if getattr(self, '_i22', None) is None:
            from .units import is_2022_plus
            self._i22 = bool(is_2022_plus(self.dec.f))
        return self._i22

    def _workset_state(self):
        """(element -> workset id, workset id -> guid, default-hidden guids) for workshared files that hide a workset somewhere, else None (rvt_worksets: Global/ElemTable + PartitionTable)"""
        if getattr(self, '_wsx', 0) == 0:
            self._wsx = None
            try:
                hid_any = any(any(x == 0 for x in (vv.get('workset_vis') or {}).values()) for vv in self.doc['views'].values())
                import rvt_worksets as W
                ws = W.worksets(self.dec.f.fn)
                if hid_any or any(not w['default_visible'] for w in ws.values()):
                    self._wsx = ({int(e): w for e, w in W.element_worksets(self.dec.f.fn).items()}, {w['id']: g for g, w in ws.items()}, {g for g, w in ws.items() if not w['default_visible']})
            except Exception: self._wsx = None
        return self._wsx

    def workset_hidden(self, v, eid):
        st = self._workset_state()
        if st is None: return False
        ew, id2g, dflt = st
        g = id2g.get(ew.get(eid))
        if g is None: return False
        m = v.get('workset_vis') or {}
        return (m[g] == 0) if g in m else (g in dflt)

    def _datum_bbox(self, eid):
        """world bbox [[min],[max]] of a datum plane's finite envelope"""
        r = self.dec.f.rec(eid); srf = ob((r or {}).get('fields', {}).get('m_pSurface')) or {}
        env = path(srf, 'm_Envelope', 'm_corners')
        if not (srf.get('m_origin') and srf.get('m_xVec') and srf.get('m_yVec') and env): return None
        o = np.asarray(srf['m_origin'], float); x = np.asarray(srf['m_xVec'], float); y = np.asarray(srf['m_yVec'], float); (a0, b0), (a1, b1) = env
        P = np.array([o + x * a + y * b for a in (a0, a1) for b in (b0, b1)])
        return np.array([P.min(0), P.max(0)])

    def _active_clip_boxes(self):
        """clip boxes of 3D views whose section box is switched on: listed in every model view (Snowdon: the 6 'Structure Only ...' boxes with sb on, none of the 7 off ones; Residential 157965)"""
        if getattr(self, '_acb', None) is None:
            self._acb = {(vv.get('section_box') or {}).get('id') for vv in self.doc['views'].values() if (vv.get('section_box') or {}).get('on')}
        return self._acb

    def _callout_views(self):
        """views that are callouts (Section records with creation method 202): their crop keeps the stored near bound"""
        if getattr(self, '_cv', None) is None:
            self._cv = {self.dec.f.eid(r['fields'].get('m_dbViewId')) for r in self.dec.f.recs('Section') if r['fields'].get('m_sectionCreationMethod') == 202}
        return self._cv

    def _jog_pieces(self, v, crop):
        """jogged section line (viewer m_frontCut): [(near plane z in the crop frame, (x0, x1) range in the crop frame)] per straight piece"""
        try:
            r = self.dec.f.rec(v['viewer']); fc = r['fields'].get('m_frontCut') if r else None
        except Exception: return None
        if not fc or len(fc) < 3: return None
        O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Z = np.asarray(v['dir'], float)
        co = np.asarray(crop['origin'], float); B = np.asarray(crop['basis'], float)
        P = [((np.asarray(q, float) - O) @ X, (np.asarray(q, float) - O) @ Z) for q in fc]
        segs = sorted((min(a[0], b[0]), max(a[0], b[0]), 0.5 * (a[1] + b[1])) for a, b in zip(P, P[1:]) if abs(a[1] - b[1]) < 1e-6 and abs(a[0] - b[0]) > 1e-6)
        if len(segs) < 2: return None
        out = []
        for i, (u0, u1, w) in enumerate(segs):
            pt = O + Z * w
            x0 = -1e9 if i == 0 else float((O + X * u0 - co) @ B[0]); x1 = 1e9 if i == len(segs) - 1 else float((O + X * u1 - co) @ B[0])
            out.append((float((pt - co) @ B[2]), (min(x0, x1), max(x0, x1))))
        return out

    def _crop_test(self, crop, use_z=True, xy=True, z=True, near0=False, near=None, xr=None):
        """oriented box test in the crop frame: x/y = crop region (when xy), z: near plane (bounds min) always for sections, far plane (bounds max) when active"""
        o = np.asarray(crop['origin'], float); B = np.asarray(crop['basis'], float); b = crop['bounds']
        lo = np.array([b[i][1] for i in range(3)], float); hi = np.array([b[i][0] for i in range(3)], float)
        if use_z and near is not None: lo[2] = near
        if xr is not None: lo[0] = max(lo[0], xr[0]); hi[0] = min(hi[0], xr[1])
        if use_z and near0 and os.environ.get('RVT_NEAR0', '1') == '1': lo[2] = max(lo[2], 0.0)       # the cut plane is the near clip of a section: nothing between it and the viewer is drawn (Residential building section: stairs / doors 1.5-13 ft in front, 80% of their ink absent from Revit's DXF)
        act = crop.get('active') or [[1, 1]] * 3
        use_lo = np.array([xy, xy, use_z]); use_hi = np.array([xy, xy, use_z and bool(act[2][0]) if z != 'all' else True])
        def test(bb):
            corners = np.array([[bb[i][0], bb[j][1], bb[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
            loc = (corners - o) @ B.T
            mn = loc.min(0); mx = loc.max(0)
            return bool(np.all((~use_hi | (mn <= hi + 1e-6)) & (~use_lo | (mx >= lo - 1e-6))))
        return test

    def _straddles(self, v, bb):
        """world AABB crosses the boundary of the view's crop box (not wholly inside it): only these need the mesh test"""
        c = v.get('crop') or {}
        if not c.get('basis'): return False
        o = np.asarray(c['origin'], float); B = np.asarray(c['basis'], float); b = c['bounds']
        lo = np.array([b[i][1] for i in range(3)], float); hi = np.array([b[i][0] for i in range(3)], float)
        L = (np.array([[bb[i][0], bb[j][1], bb[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)]) - o) @ B.T
        ulo, uhi = self._box_use(c)
        return not bool(np.all((~ulo | (L >= lo - 1e-6)) & (~uhi | (L <= hi + 1e-6))))

    @staticmethod
    def _box_use(c):
        xy = bool(c.get('crop_active')); act = c.get('active') or [[1, 1]] * 3
        return np.array([xy, xy, True]), np.array([xy, xy, bool(act[2][0])])

    def _mesh_in_box(self, v, eid):
        """any mesh triangle of the element (AABB in the crop frame) overlaps the crop box; True when the mesh is unavailable"""
        try:
            import rvt_elemmesh as E_
            T = np.asarray(E_.element_mesh(self.dec.f.g, eid).get('tris') or [], float).reshape(-1, 3, 3)
            if not len(T): return True
            c = v['crop']; o = np.asarray(c['origin'], float); B = np.asarray(c['basis'], float); b = c['bounds']
            lo = np.array([b[i][1] for i in range(3)], float); hi = np.array([b[i][0] for i in range(3)], float)
            L = ((T.reshape(-1, 3) - o) @ B.T).reshape(-1, 3, 3)
            ulo, uhi = self._box_use(c)
            return bool(np.any(np.all((~ulo | (L.max(1) >= lo - 1e-6)) & (~uhi | (L.min(1) <= hi + 1e-6)), axis=1)))
        except Exception: return True

    def _level_z(self, eid):
        """a level's view-vertical coordinate (along the view's up axis from the view origin)"""
        r = self.dec.f.rec(eid, 'Level')
        if not r: return None
        srf = ob(r['fields'].get('m_pSurface')) or {}
        if not srf.get('m_origin'): return None
        v = self._cur_view
        return float((np.asarray(srf['m_origin'], float) - np.asarray(v['origin'], float)) @ np.asarray(v['up'], float))

    def elements(self, vid, explain=False):
        v0 = self.doc['views'].get(vid) or self.doc['views'].get(str(vid))
        v = self.effective(v0); self._cur_view = v0
        hid, xflags = self.hidden_categories(v); shown_opts = self.shown_options(v0)
        hidden_el = set(v0.get('hidden_elements') or [])
        pf = self.pfilters.get(v.get('phase_filter'))
        self._loose_vol = None; vol = self.volume(v)
        crop_v = None
        if v['kind'] == 'section' and (v.get('crop') or {}).get('crop_active'):
            try:
                from .compose import crop_rect_uv
                cr_ = crop_rect_uv(v)
                if cr_ is not None: crop_v = (float(cr_[1]), float(cr_[3]))
            except Exception: crop_v = None
        out = {}; why = {}
        for eid, e in self.info.info.items():
            if not e['has_header'] and e['cls'] in ('Level', 'Grid') and not e['type']:
                # some datums (2020 Residential level 'first floor') have no element header: category from the class, shown by default
                e = dict(e, cat={'Level': -2000240, 'Grid': -2000220}[e['cls']], vflags=1, has_header=True)
            prim_ = v.get('primary') if os.environ.get('RVT_DEPENDENT', '1') == '1' else None
            if prim_ in (None, INVALID, -1) or v['kind'] != 'plan': prim_ = None
            own_ = vid if prim_ is None or e['owner'] != prim_ else e['owner']         # a dependent view lists the view-specific elements of its primary view too (2024 rosetta 'dependent': text note + datum extent of the primary)
            if prim_ is not None and e['cls'] == 'Viewer' and self.dec.f.eid((self.dec.f.rec(eid) or {'fields': {}})['fields'].get('m_dbViewId')) == vid: out[eid] = None; continue      # a dependent view lists its own viewer element
            if e['cls'] == 'ExtentElem' and e['owner'] in (vid, prim_) and v['kind'] != 'graphical_column_schedule' and os.environ.get('RVT_VIEW_META', '1') == '1': out[eid] = None; continue      # the view's own datum-extent element is in its list in every view (Residential 25/25, Commercial 24/24)
            if e['type'] or not e['has_header']: continue
            if e.get('cat') == -2000262 and os.environ.get('RVT_CONSTRAINTS', '0') != '1': why[eid] = 'constraint_dimension'; continue      # Constraints (alignment / equality) are drawn only in 'show constraints' mode: 91 such elements in the 4 oracle files, 0 in any Revit view list (Snowdon 916437: blue 1 1/2" dimensions)
            if e.get('fam', INVALID) != INVALID and os.environ.get('RVT_FAMWALL', '1') == '1': why[eid] = 'family_member_wall'; continue      # walls with a Family id (in-place family content, Residential 201264 / 205606-8): Revit lists them in no view
            if e['owner'] not in (INVALID, vid, prim_): continue
            if v['kind'] == 'graphical_column_schedule' and e['owner'] != vid and (e['cls'] in ('Level', 'GraphSchedColumnTable') or (e['cls'] == 'FamilyInstance' and e['cat'] == -2001330)) and os.environ.get('RVT_GCS', '1') == '1': out[eid] = None; continue      # a graphical column schedule lists every structural column and every level (rst_basic: 30 of 30 + 9 of 9)
            if v['kind'] in OWNED_ONLY_KINDS and e['owner'] not in (vid, prim_): continue
            if v['kind'] == '3d' and e['cls'] in MARKER_CLASSES: why[eid] = 'marker_in_3d'; continue
            if e['cls'] == 'ModelClipBox' and eid in self._active_clip_boxes() and e['cat'] not in hid and v['kind'] not in OWNED_ONLY_KINDS and os.environ.get('RVT_VIEW_META', '1') == '1': out[eid] = None; continue      # one project-wide clip box (lowest id) is listed in every model view
            if e['cls'] == 'ModelClipBox' and (v.get('section_box') or {}).get('id') != eid: why[eid] = 'other_views_section_box'; continue
            if e['cls'] == 'ModelClipBox' and not (v.get('section_box') or {}).get('on') and eid not in self._active_clip_boxes() and os.environ.get('RVT_BOX_OFF', '1') == '1': why[eid] = 'section_box_off'; continue      # a 3D view's own section box is listed only while it is active (Residential: the 5 inactive boxes of 5 views unlisted)
            if e['cls'] == 'Level' and v['kind'] == 'section' and crop_v is not None:
                lz = self._level_z(eid)
                if lz is not None and not (crop_v[0] - 1e-6 <= lz <= crop_v[1] + 1e-6): why[eid] = 'level_outside_crop'; continue     # a level appears in a section / elevation only when its elevation lies in the crop's vertical range (all views of 4 samples)
            if e['cls'] in NEVER_CLASSES and not (e['cls'] == 'ReferencePoint' and v['kind'] == '3d' and os.environ.get('RVT_REFPOINT_3D', '1') == '1'): why[eid] = 'never_drawn_class'; continue
            if e['cls'] in ('Viewport', 'GCSViewport') and e['owner'] != vid: why[eid] = 'viewport_not_on_this_sheet'; continue
            if e['cat'] in SKETCH_CATS: why[eid] = 'sketch_line'; continue
            if e['cat'] == AREA_BOUNDARY:
                ok_ = v.get('class') == 'DBViewPlan' and (v.get('range') or {}).get('plan_view_type') == 4
                vt_ = self.dec.f.rec(v.get('view_type')) if v.get('view_type') not in (None, INVALID, -1) else None
                if vt_ is not None and vt_['class'] == 'DBViewTypeAreaPlan':       # area plan (Residential 'first floor' area plan): the boundaries of its own area scheme
                    sch_ = self.dec.f.eid(vt_['fields'].get('m_areaMeasureElemId')); cr_ = self.dec.f.rec(eid)
                    ok_ = ok_ or (cr_ is not None and self.dec.f.eid(cr_['fields'].get('m_areaSchemeId')) == sch_)
                if not ok_: why[eid] = 'area_boundary_outside_area_plan'; continue
            if e['cls'] == 'Level' and (v['kind'] == 'plan' or (v['kind'] == '3d' and (os.environ.get('RVT_3D_DATUMS', '1') != '1' or not self._is22()))): why[eid] = 'level_in_plan_or_3d'; continue
            if v['kind'] == '3d' and e['cls'] in ('Grid', 'RefPlane', 'Level'):
                if e['cls'] == 'RefPlane' or os.environ.get('RVT_3D_DATUMS', '1') != '1' or not self._is22(): why[eid] = 'datum_in_3d'; continue         # 3D views list grids and levels (Snowdon 'Structure Only' 34), never reference planes
                if e['cls'] == 'Grid' and (v.get('crop') or {}).get('crop_active') and os.environ.get('RVT_CROP3D_GRIDS', '0') != '1': why[eid] = 'grid_in_cropped_3d'; continue       # Snowdon 2026 'CoverSheet' (cropped orthographic 3D): 0 of its 15 grids listed by Revit, like every cropped 3D view of the oracle files (14 views)
                if e['cls'] == 'Grid' and (v.get('section_box') or {}).get('on') and os.environ.get('RVT_BOX_GRIDS', '0') != '1': why[eid] = 'grid_in_section_box_view'; continue       # Snowdon: the 6 boxed 3D views list their 2-4 levels, never a grid (grids are 2D-extent datums: their 3D line is outside the box)
                bb_ = self._datum_bbox(eid)
                if bb_ is not None and not vol(bb_): why[eid] = 'datum_outside_section_box'; continue
            if eid in hidden_el: why[eid] = 'hidden_element'; continue
            if os.environ.get('RVT_WORKSETS', '1') == '1' and self.workset_hidden(v0, eid): why[eid] = 'workset_hidden'; continue
            if e['cls'] == 'RoomElem' and os.environ.get('RVT_ROOMS', '1') == '1':
                if v['kind'] == '3d': why[eid] = 'room_in_3d'; continue                  # Residential: 0 rooms in 6 of 6 3D lists (102 predicted)
                bb_ = self.info.bbox(eid); rg_ = v.get('range') or {}
                if bb_ is not None and (not np.all(bb_[0] <= bb_[1]) or np.abs(bb_).max() > 1e20): bb_ = None      # unplaced room (empty bbox sentinel): listed by Revit
                if v['kind'] == 'plan' and bb_ is not None and rg_.get('cut') is not None and rg_.get('plan_view_type') != 2 and (bb_[1][2] < rg_['cut'] - 1e-6 or bb_[0][2] > rg_['cut'] + 1e-6): why[eid] = 'room_not_at_cut'; continue      # a room is listed in a plan only when it spans the cut plane (Residential: first floor cut 4, rooms 0..8 listed, the basement rooms -8..-1 not; attic 13 / Site 32.8)
            if e['cls'] == 'RoomElem' and v['kind'] == 'section' and (v.get('crop') or {}).get('basis') and os.environ.get('RVT_ROOM_SECTION', '1') == '1' and not self._room_on_cut_line(eid, v):
                why[eid] = 'room_not_on_section_line'; continue      # a room is listed in a section only where the section line crosses it (Residential: cross section lists the 4 rooms spanning the cut plane, 7 rooms behind it unlisted; building section = jogged line)
            if e['cls'] == 'FaceSplitter' and v['kind'] == 'section' and v.get('dir') is not None and v.get('discipline') != 2 and os.environ.get('RVT_SPLIT_EDGEON', '1') == '1':
                try:
                    sk_ = self.dec.f.rec(self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_sketchId')))['fields']['m_pPlane']['obj']
                    n_ = np.cross(np.asarray(sk_['m_xVec'], float), np.asarray(sk_['m_yVec'], float)); n_ /= max(np.linalg.norm(n_), 1e-12)
                    if abs(float(n_ @ np.asarray(v['dir'], float))) < 0.2: why[eid] = 'split_face_edge_on'; continue      # a split line is listed in a section only when its host face faces the viewer (Residential: N/S sections list the wall splits, E/W and the cross section none; floor splits in no section)
                except Exception: pass
            if e['cls'] in ('InteriorElev', 'InteriorElevArrow') and v['kind'] == 'plan' and (v.get('crop') or {}).get('crop_active') and os.environ.get('RVT_MARKER_CROP', '1') == '1':
                try:
                    from .compose import crop_rect_uv
                    cr_ = crop_rect_uv(v); fl_ = self.dec.f.rec(eid)['fields']
                    pos_ = fl_.get('m_pos') or fl_.get('m_targetPos')
                    if cr_ is not None and pos_ is not None:
                        O_ = np.asarray(v['origin'], float); X_ = np.asarray(v['right'], float); Y_ = np.asarray(v['up'], float); q_ = np.asarray(pos_, float) - O_
                        u_, w_ = float(q_ @ X_), float(q_ @ Y_)
                        if not (cr_[0] <= u_ <= cr_[2] and cr_[1] <= w_ <= cr_[3]): why[eid] = 'marker_outside_crop'; continue      # elevation markers outside a plan's crop region are not listed (Commercial Enlarged Toilet Rooms 1 of 5, Mezzanine 0 of 4)
                except Exception: pass
            if e['cls'] == 'Viewer3d' and os.environ.get('RVT_CAMERA_DISC', '1') == '1' and v.get('discipline') is not None:
                dc_ = self._camera_disc(eid); dv_ = v.get('discipline')
                if dc_ is not None and not (dv_ == dc_ or dv_ == 4095 or dc_ == 4095):
                    why[eid] = 'camera_other_discipline'; continue
                if os.environ.get('RVT_OWN_CAMERA', '0') == '1' and v['kind'] == '3d' and dv_ != 2 and self.dec.f.eid((self.dec.f.rec(v['id']) or {'fields': {}})['fields'].get('m_viewerId')) == eid: why[eid] = 'own_camera'; continue      # a 3D view does not list its own camera (structural '3D View n' do)      # a 3D view's camera is listed only in views of the same discipline (rst_basic: cameras of the 4 structural '3D View n' only in structural views; discipline 4095 = all)
            if e['cls'] in ('LineLoad', 'AreaLoad', 'PointLoad') and v['kind'] == '3d' and os.environ.get('RVT_LOADS', '1') == '1': why[eid] = 'loads_not_listed'; continue      # structural loads are in no 3D view list (rst_basic: 0 of 40 predicted in the analytical 3D view; plans list them)
            if e['cls'] == 'WallSweep' and v['kind'] == 'plan' and (v.get('range') or {}).get('plan_view_type') != 2 and v['range'].get('bottom') is not None and abs(v['range']['bottom']) < 1e8 and v.get('discipline') != 2 and os.environ.get('RVT_SWEEP_UNDERLAY', '1') == '1':
                bb_ = self.info.bbox(eid)
                if bb_ is not None and bb_[1][2] < min(v['range']['bottom'], v['range'].get('depth') if v['range'].get('depth') is not None else v['range']['bottom']) - 1e-6: why[eid] = 'sweep_in_underlay_only'; continue      # wall sweeps wholly below the primary range (underlay only) are unlisted (Residential attic plan: 8 of 8)
            if e['cls'] == 'WallSweep' and v['kind'] == 'plan' and (v.get('range') or {}).get('plan_view_type') == 2 and v['range'].get('cut') is not None and os.environ.get('RVT_RCP_SWEEPS', '1') == '1':
                bb_ = self.info.bbox(eid)
                if bb_ is not None and bb_[1][2] < v['range']['cut'] - 1e-6: why[eid] = 'sweep_below_rcp_cut'; continue      # reflected ceiling plans list walls below their cut (underlay) but not wall sweeps / reveals (Residential first floor + attic RCPs: 16 of 16 unlisted)
            if v['kind'] == 'section' and e['cls'] == 'VolumeOfInterest' and os.environ.get('RVT_VOI_SECTION', '1') == '1': why[eid] = 'scope_box_in_section'; continue       # Snowdon: 0 of 20 section lists hold a scope box (12 predicted)
            if v.get('discipline') == 2 and e['cls'] == 'SWall' and os.environ.get('RVT_STRUCT_WALLS', '1') == '1':
                fl_ = self.dec.f.rec(eid)['fields']
                if not fl_.get('m_isStructuralSignificant'): why[eid] = 'nonstructural_wall_in_structural_view'; continue       # Structural discipline views list only structurally significant walls (oracle scene 2024_vg_discipline: 5 of 5 walls with significance 0 unlisted; Snowdon L2: 21 of 21 significant listed)
            if v['kind'] == '3d' and e['cls'] in NOT_IN_3D and os.environ.get('RVT_NOT_IN_3D', '1') == '1' and self._is22(): why[eid] = 'not_in_3d'; continue
            if e['cls'] == 'FaceSplitter' and v['kind'] == 'plan' and (v.get('range') or {}).get('plan_view_type') != 2 and (v.get('range') or {}).get('top') is not None and os.environ.get('RVT_SPLITTER_CUT', '1') == '1':
                # split-face lines lying inside a floor plan's view range are not listed, those below the range (attic plan) or in ceiling plans are (Residential: 32 / 180203 / site plan 7 FP, attic + ceiling plan 7 TP)
                sb_ = self.info.bbox(eid); rg_ = v['range']; zl_ = min(x for x in (rg_.get('depth'), rg_.get('bottom')) if x is not None)
                if sb_ is not None and min(sb_[1][0] - sb_[0][0], sb_[1][1] - sb_[0][1]) < 1e-3 and sb_[1][2] >= zl_ - 1e-6 and sb_[0][2] <= rg_['top'] + 1e-6: why[eid] = 'splitter_in_range'; continue
            if e['cls'] == 'RefPlane' and self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_designOptionId')) == -4: why[eid] = 'refplane_dopt4'; continue       # reference planes with design option id -4 (Commercial 52, Residential 8) are in no Revit list; those with -1 are (rst_basic 21, Snowdon 16, Residential 2)
            if v['kind'] == 'section' and e['cls'] in DATUM_CLASSES and v.get('dir') and not self._datum_perpendicular(eid, v): why[eid] = 'datum_not_perpendicular'; continue
            if v['kind'] == 'plan' and e['cls'] == 'RefPlane' and v.get('dir') and os.environ.get('RVT_REFPLANE_PLAN', '1') == '1' and not self._datum_perpendicular(eid, v): why[eid] = 'refplane_not_vertical'; continue      # plans list only vertical reference planes (rst_basic Roof Level / Top of Parapet / Ref Beam system: the 4 horizontal and 2 slanted planes unlisted)
            if (v['kind'] == 'section' or (v['kind'] == 'plan' and e['cls'] == 'Grid' and os.environ.get('RVT_GRID_CROP_PLAN', '1') == '1')) and e['cls'] in ('Grid', 'RefPlane') and not self._datum_meets_crop(eid, v): why[eid] = 'datum_outside_crop'; continue
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
            if c == INVALID and e['cls'] == 'CoordinateSystemDisplayElem' and os.environ.get('RVT_CSDE', '1') == '1' and v['kind'] in ('plan', 'section', '3d'):
                if self._origin_in_view(v, vol): out[eid] = None
                else: why[eid] = 'origin_outside_view'
                continue
            if c == INVALID: why[eid] = 'no_category'; continue
            if not (e['vflags'] or 0) & 1: why[eid] = 'view_flags'; continue
            par = (self.cats.get(c) or {}).get('parent', INVALID)
            ct = CAT_TYPES.get(c) or CAT_TYPES.get(par)
            if e['cls'] == 'PropertyLineSegment':
                # Revit lists and draws them (site plans) although their own category is internal, only inside the PRIMARY view range (not the underlay, not ceiling plans)
                rg = v.get('range') or {}; bb = self.info.bbox(eid)
                # DXF of Residential / Commercial plans (14 views): property lines are in the views whose crop volume reaches 1000 ft ('bounds' z [1000, 0.1]: Level 1 157296, first floor 180203, Mezzanine
                # ceiling plan 214395, none in the [100, 0] ones: 32 / 36 / attic) and in site plans (range top 200); RVT_PROPLINE_Z=0 restores the range rule
                zb_ = ((v.get('crop') or {}).get('bounds') or [None, None, [0]])[2][0]
                legacy_ = os.environ.get('RVT_PROPLINE_Z', '1') != '1'
                candidate_ = property_line_candidate(
                    v['kind'], rg.get('plan_view_type'), rg.get('top'), zb_,
                    legacy=legacy_, bbox_z=None if bb is None else bb[0][2],
                    range_bottom=rg.get('bottom'), range_depth=rg.get('depth'))
                if not candidate_ and not legacy_ and os.environ.get('RVT_PROPLINE_LIST', '1') == '1':
                    # the element LIST follows Revit's collector (range rule too: Residential 'first floor' 32 lists 4 segments the DXF does not draw); drawing keeps the stricter rule (viewdraw)
                    candidate_ = property_line_candidate(
                        v['kind'], rg.get('plan_view_type'), rg.get('top'), zb_, legacy=True, bbox_z=None if bb is None else bb[0][2],
                        range_bottom=rg.get('bottom'), range_depth=rg.get('depth'))
                if bb is None or not candidate_:
                    # Preserve the distinction between range and eligibility exclusions.
                    why[eid] = ('property_line_range' if legacy_ and bb is not None
                                and v['kind'] == 'plan' and rg.get('plan_view_type') != 2
                                and rg.get('top') is not None else 'property_line_rule')
                    continue
                ct = None
            if ct == 'Internal' or (ct in TYPE_FLAG and xflags.get(TYPE_FLAG[ct])): why[eid] = 'category_type_' + str(ct); continue
            if c in hid or par in hid: why[eid] = 'category_hidden'; continue
            if e.get('rphase', INVALID) not in (INVALID, None) and v.get('phase') not in (None, INVALID) and e['rphase'] != v['phase'] and os.environ.get('RVT_ROOM_PHASE', '1') == '1':
                why[eid] = 'room_phase'; continue         # rooms exist in their own phase only (2024 rosetta markers scene: the room is listed in the views of its phase, not in the duplicates of another phase)
            if e['cls'] == 'Viewer3d' and os.environ.get('RVT_VIEWER3D_PHASE', '1') == '1':
                tv3_ = self.doc['views'].get(self.dec.f.eid((self.dec.f.rec(eid) or {'fields': {}})['fields'].get('m_dbViewId')))
                if tv3_ and tv3_.get('phase') not in (None, INVALID, -1) and v.get('phase') not in (None, INVALID, -1) and tv3_['phase'] != v['phase']:
                    why[eid] = 'viewer3d_phase'; continue         # a 3D view's camera element belongs to the phase of that view (2026 rosetta sheet scene: listed only in the phase-7019 plan)
            st = self.phase_status(e, v.get('phase'))
            if st in ('past', 'future'): why[eid] = 'phase_' + st; continue
            if st and pf and pf.get('presentation'):
                if pf['presentation'][PHASE_IDX[st]] == DONT_SHOW: why[eid] = 'phase_filter_' + st; continue
            if e['dopt'] not in (INVALID,) and e['dopt'] != -4 and self.primary_options and e['dopt'] not in shown_opts: why[eid] = 'design_option'; continue
            if e['owner'] == INVALID:
                bb = self.info.bbox(eid)
                if bb is not None and e['cls'] == 'PropertyLineSegment' and v['kind'] == 'plan' and (v.get('range') or {}).get('plan_view_type') == 2 and os.environ.get('RVT_PROPLINE_Z', '1') == '1':
                    bb = np.array([[bb[0][0], bb[0][1], v['range']['cut']], [bb[1][0], bb[1][1], v['range']['cut']]])       # ceiling plan: property lines are tested against the crop only
                nobox_ = bb is not None and e['cls'] == 'PartMaker' and not np.all(bb[0] <= bb[1])      # division makers without extent are listed in every view (rst_basic: 8 of 8 in all 32 views)
                unplaced_room_ = bb is not None and e['cls'] == 'RoomElem' and not np.all(bb[0] <= bb[1]) and os.environ.get('RVT_ROOM_UNPLACED', '1') == '1'
                if unplaced_room_:
                    bb = None
                    rp_ = self.dec.f.eid((self.dec.f.rec(eid)['fields']).get('m_phaseId'))
                    if rp_ not in (None, INVALID) and v.get('phase') not in (None, INVALID) and rp_ != v.get('phase'): why[eid] = 'unplaced_room_other_phase'; continue      # an unplaced room belongs to one phase and is listed only in views of that phase (VG phases scene: Phase 3 views only)      # unplaced room (empty bbox sentinel): listed in every plan / section (VG phases scene: 9 FN)
                if bb is not None and e['cls'] == 'PropertyLineSegment' and v['kind'] == 'plan' and os.environ.get('RVT_PROPLINE_NOVOL', '1') == '1' and property_line_candidate('plan', 1, (v.get('range') or {}).get('top'), ((v.get('crop') or {}).get('bounds') or [None, None, [0]])[2][0]): nobox_ = True       # deep-crop views list the segments whatever the crop rectangle (Residential basement 156499: 4 of 4 listed, crop does not reach them)
                if bb is not None and e['cls'] == 'CoordinateSystemDisplayElem' and v['kind'] == 'plan' and os.environ.get('RVT_COORD_ELEM', '1') == '1':
                    if (v.get('crop') or {}).get('crop_active'): why[eid] = 'coord_elem_cropped'; continue       # Snowdon: the 9 plans with an active crop region do not list it
                    nobox_ = True       # the origin marker is listed in every plan that shows its category whatever the view range (Snowdon: 12 plans above / below z 0 listed)
                if bb is not None and not nobox_ and not vol(bb) and not (e['cls'] in ('StairsElement', 'StairsRun', 'StairsSupport') and v['kind'] == 'section' and getattr(self, '_loose_vol', None) is not None and os.environ.get('RVT_JOG_STAIRS', '1') == '1' and self._loose_vol(bb)): why[eid] = 'outside_view_volume'; continue
                if bb is not None and not nobox_ and v['kind'] == 'section' and e['cls'] == 'FamilyInstance' and os.environ.get('RVT_MESH_BOX', '0') == '1' and self._straddles(v, bb) and not self._mesh_in_box(v, eid):
                    why[eid] = 'mesh_outside_view_volume'; continue       # rotated members whose world box overlaps the section volume while none of their triangles does (Snowdon Sawtooth sections: 4 of 4 omitted framing members had no triangle in the box)
                if bb is not None and e['cls'] in ('StairsRun', 'StairsElement', 'StairsSupport') and v['kind'] == 'plan' and v.get('range') and v['range'].get('plan_view_type') != 2 and v['range'].get('cut') is not None and os.environ.get('RVT_STAIR_ABOVE_CUT', '1') == '1' and v.get('discipline') != 2 and bb[0][2] > v['range']['cut'] + 1e-3:
                    why[eid] = 'stair_above_cut'; continue      # a stair lying wholly above the cut plane is not listed in the plan (Residential basement: descending stair 0..-1.5 above cut -4)
                sbx_ = v.get('section_box')
                if bb is not None and v['kind'] == '3d' and sbx_ and sbx_.get('on') and e['cls'] == 'FamilyInstance' and (self.doc['categories'].get(e['cat']) or {}).get('name') == 'Planting' and os.environ.get('RVT_PLANT_CENTRE', '1') == '1':
                    o_ = np.asarray(sbx_['origin'], float); B_ = np.asarray(sbx_['basis'], float); bn_ = sbx_['bounds']
                    c_ = ((bb[0] + bb[1]) / 2 - o_) @ B_.T
                    if not all(bn_[i][1] <= c_[i] <= bn_[i][0] for i in range(3)): why[eid] = 'planting_centre_outside_box'; continue      # RPC plantings (huge bboxes) are listed in a boxed 3D view only with their centre inside the box (Residential {3D}: 2 of 3 outside plantings were listed)
                if bb is not None and v['kind'] == 'plan' and v.get('range') and v['range'].get('plan_view_type') != 2 and v['range'].get('cut') is not None and bb[0][2] > v['range']['cut'] + 1e-3 and e['cls'] not in ABOVE_CUT_KEEP and e['cat'] not in ABOVE_CUT_KEEP_CATS and os.environ.get('RVT_ABOVE_CUT_ALL', '1') == '1' and v.get('discipline') != 2:
                    why[eid] = 'wholly_above_cut'; continue      # elements wholly above the cut plane are listed by Revit only for beam systems / generic models (Residential 9 of 10 unlisted: roofs, fascias, railings, equipment, split faces; rst_basic doors 2)
                if bb is not None and e['cls'] in ('ContFooting', 'BuildingPad') and v['kind'] == 'plan' and v.get('range') and (v['range'].get('cut') or 0) < 100 and os.environ.get('RVT_FOOT_TOUCH', '1') == '1' and v.get('discipline') != 2:
                    zbs_ = [x for x in (v['range'].get('bottom'), v['range'].get('depth'), v['range'].get('underlay_bottom')) if x is not None and abs(x) < 1e8]
                    if any(abs(bb[1][2] - x) < 1e-3 for x in zbs_) and bb[1][2] <= min(zbs_) + 1e-3: why[eid] = 'footing_touches_range_bottom'; continue      # continuous footings whose top only touches the range bottom (Residential basement / first floor: 6 of 6 unlisted; rst_basic footings inside the range listed)
                if bb is not None and e['cat'] in ABOVE_CUT_CATS and v['kind'] == 'plan' and v.get('range') and v['range'].get('plan_view_type') != 2 and os.environ.get('RVT_FRAME_ABOVE', '1') == '1':
                    cz_ = v['range'].get('cut')
                    if cz_ is not None and bb[0][2] > cz_ + 0.01: why[eid] = 'above_cut'; continue          # wholly above the plan's cut plane: never in Revit's list (framing 468 / columns 48 / rebar 30 / foundations 6 / connections 16 / floors 12 predicted, 0 listed, over every oracle plan of 4 files; walls are mixed and stay)
                if bb is not None and e['cat'] == -2001120 and v['kind'] == 'plan' and v.get('range') and (v['range'].get('plan_view_type') != 2):
                    # ceiling-hosted lighting fixtures wholly above the cut plane are not in a floor plan (Residential plans 32 / 180203 / basement: collector lists none; the ceiling plan, whose cut plane is at the ceiling, lists them)
                    cz = v['range'].get('cut')
                    if cz is not None and bb[0][2] >= cz - 1e-6: why[eid] = 'above_cut_lighting'; continue
                room_nobox_ = bb is None and e['cls'] == 'RoomElem' and v['kind'] == 'plan' and os.environ.get('RVT_ROOM_NOBOX', '1') == '1' and vid == max([k for k in self._nobox_room_plans(self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_levelId'))) if k < eid] or [None], key=lambda k: -1 if k is None else k)      # a room without extent (not placed, no bbox) is listed in ONE uncropped floor plan of its level: the newest candidate older than the room (the plan it was created in; element ids are chronological). Snowdon 7 of 7, Commercial 1 of 1, Residential 1 of 1
                if bb is None and e['cls'] not in DATUM_CLASSES and e['cls'] not in ('Viewer3d', 'ExtentElem', 'ModelClipBox') and not room_nobox_ and not (e['cls'] == 'RvtLinkInstance' and (os.environ.get('RVT_LINK_LISTED', '0') == '1' or (os.environ.get('RVT_LINK_NOBOX', '1') == '1' and self._link_visible(eid, vid)))) and not (e['cls'] == 'RoomElem' and unplaced_room_): why[eid] = 'no_graphics_no_bbox'; continue
            out[eid] = st
        if os.environ.get('RVT_TAG_HOST', '1') == '1':
            for eid in [k for k in out if self.info.info[k]['cls'] in ('IndependentTag', 'RoomTag')]:           # a tag whose tagged element is not in the view is not listed either (room tags: m_taggedRoomElemId, rooms of another phase)
                try:
                    tf_ = self.dec.f.rec(eid)['fields']
                    h = self.dec.f.eid(ob(tf_.get('m_taggedElementId') or tf_.get('m_taggedRoomElemId')).get('m_linkInstOrHostId'))
                except Exception: continue
                if h not in (None, INVALID) and h in self.info.info and self.info.info[h]['owner'] == INVALID and h not in out and (self.info.info[eid]['cls'] != 'RoomTag' or self.info.info[h].get('rphase', INVALID) not in (INVALID, None)):
                    del out[eid]; why[eid] = 'tagged_element_not_in_view'
        if os.environ.get('RVT_DIM_REFS', '1') == '1':
            rgp = v.get('range') or {}
            for eid in [k for k in out if self.info.info[k]['cls'] == 'LinearDimString']:       # same rules as annot.dimension: Revit lists no dimension whose references are all dangling / whose referenced element is not in the view / whose plane lies below a plan's range
                fl = self.dec.f.rec(eid)['fields']; wr = fl.get('m_witnessRefs') or []; refs = []
                for w in wr:
                    try: refs.append(self.dec.f.eid((wref(w).get('m_geomRef') or {}).get('m_elemId')))
                    except Exception: refs.append(None)
                if os.environ.get('RVT_DIM_LINKREF', '1') == '1' and os.environ.get('RVT_LINK_LISTED', '0') != '1' and any(x in self.info.info and self.info.info[x]['cls'] == 'RvtLinkInstance' for x in refs): del out[eid]; why[eid] = 'dim_ref_in_unloaded_link'; continue      # dimensions that reference geometry of a linked model are not listed when the link was unloaded at export (Snowdon L1_43_High: 20 of 20 FP dimensions, 0 of the TP ones)
                if wr and all(x in (None, INVALID, -1) for x in refs): del out[eid]; why[eid] = 'dim_dangling_refs'; continue
                if self.dec.f.idbits == 64 and os.environ.get('RVT_DIMREF64', '0') == '1' and any(x not in (None, INVALID, -1) and x in self.info.info and self.dec.f.rec(x) is None for x in refs): del out[eid]; why[eid] = 'dim_ref_no_record'; continue
                if os.environ.get('RVT_DIM_REFVIEW', '1') == '1' and (self.dec.f.idbits == 32 or os.environ.get('RVT_DIMREF64', '0') != '1') and any(x not in (None, INVALID, -1) and x in self.info.info and self.info.info[x]['owner'] == INVALID and x not in out and why.get(x) == 'outside_view_volume' for x in refs): del out[eid]; why[eid] = 'dim_ref_not_in_view'; continue
                dl = ob(fl.get('m_pDimLine')) or {}
                if v['kind'] == 'plan' and dl.get('m_origin') and rgp.get('bottom') is not None and dl['m_origin'][2] < rgp['bottom'] - 0.5: del out[eid]; why[eid] = 'dim_below_range'
        if os.environ.get('RVT_CGL_HOST', '1') == '1':
            for eid in [k for k in out if self.info.info[k]['cls'] == 'CurtainGridLine']:       # a curtain grid line is listed only with its curtain wall (Commercial detail views: 18 grid lines of walls outside the view)
                try: h = self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_hostId'))
                except Exception: continue
                if h in self.info.info and h not in out and not (v['kind'] == '3d' and os.environ.get('RVT_CGL_HOST_3D', '1') == '1'): del out[eid]; why[eid] = 'host_not_in_view'
        if os.environ.get('RVT_STAIR_PARENT', '1') == '1' and v['kind'] != 'section':
            # a stair's runs are listed only with their stair element and its supports only with their run (rst_basic: Level 1 / Level 2 / foundation / pile views list the run and supports of a stair whose element we already dropped, Revit lists none of the set)
            for eid in [k for k in out if self.info.info[k]['cls'] == 'StairsRun']:
                try: par = self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_stairsId'))
                except Exception: continue
                if par in self.info.info and par not in out: del out[eid]; why[eid] = 'stair_parent_unlisted'
            for eid in [k for k in out if self.info.info[k]['cls'] == 'StairsSupport' and (os.environ.get('RVT_STAIR_SUPPORT_PARENT', '0') == '1' or (v['kind'] == '3d' and os.environ.get('RVT_STAIR_SUPPORT_3D', '1') == '1'))]:
                try: par = self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_hostCompId'))
                except Exception: continue
                if par in self.info.info and par not in out: del out[eid]; why[eid] = 'stair_run_unlisted'
        if os.environ.get('RVT_CGL_FLATLINE', '1') == '1' and v['kind'] == 'plan':
            for eid in [k for k in out if self.info.info[k]['cls'] == 'CurtainGridLine']:      # straight horizontal grid lines are not listed in plans (Commercial 14 of 14), horizontal arcs of curved walls are (1 of 1)
                bb_ = self.info.bbox(eid)
                if bb_ is None or np.abs(bb_).max() > 1e20 or abs(bb_[1][2] - bb_[0][2]) > 1e-3: continue
                try: fc_ = ob(self.dec.f.rec(eid)['fields'].get('m_pFullCurve')) or {}
                except Exception: continue
                if fc_ and fc_.get('m_radius') is None: del out[eid]; why[eid] = 'cgl_flat_line_in_plan'
        if os.environ.get('RVT_CGL_NOBBOX', '1') == '1' and v['kind'] == 'section':
            for eid in [k for k in out if self.info.info[k]['cls'] == 'CurtainGridLine']:      # no extent known: Revit lists none of them in sections / elevations (Commercial: 77 of 77 absent, while 48 of 54 in 3D views are listed)
                bb_ = self.info.bbox(eid)
                if bb_ is None or np.abs(bb_).max() > 1e20: del out[eid]; why[eid] = 'cgl_no_bbox'
        if os.environ.get('RVT_CGL_EDGEON', '1') == '1' and v['kind'] == 'section' and v.get('right') is not None:
            # Revit lists no vertical curtain grid lines of a curtain wall seen edge-on (the wall plane contains the view direction): Commercial elevations,
            # the vertical lines of the side walls are absent while the horizontal line across the wall depth is listed
            try:
                import collections
                O_ = np.asarray(v['origin'], float); X_ = np.asarray(v['right'], float); Y_ = np.asarray(v['up'], float); Z_ = np.asarray(v['dir'], float)
                byh = collections.defaultdict(list)
                for eid in [k for k in out if self.info.info[k]['cls'] == 'CurtainGridLine']:
                    bb_ = self.info.bbox(eid)
                    if bb_ is None or abs(bb_[1][2] - bb_[0][2]) < 1e-3 or np.abs(bb_).max() > 1e20: continue
                    d_ = bb_[1] - bb_[0]
                    if abs(d_[0]) > 1e-3 or abs(d_[1]) > 1e-3: continue                   # vertical lines only
                    h = self.dec.f.eid(self.dec.f.rec(eid)['fields'].get('m_hostId'))
                    byh[h].append((eid, float((bb_[0] - O_) @ X_), float((bb_[0] - O_) @ Z_)))
                for h, L_ in byh.items():
                    if len(L_) >= 2 and max(x[1] for x in L_) - min(x[1] for x in L_) < 0.3 and max(x[2] for x in L_) - min(x[2] for x in L_) > 1.0:
                        for eid, _, _ in L_: del out[eid]; why[eid] = 'cgl_edge_on'
            except Exception: pass
        return (out, why) if explain else out
