"""Walk an element's saved graphics (channel 103) for ONE view: evaluate the node conditions for that view (direction, detail level,
cut plane), follow symbol instances with their transforms, and return world-space pieces:
  curves: [{'pts': [[x,y,z],...], 'gs': gstyle id, 'closed': bool, 'filled': bool}]
  solids: [{'geo': Geometry node dict, 'R': 3x3, 'o': origin, 'gs': gstyle id}]
  texts / fills (2D symbolic content) like gfx.Collector.
Condition semantics are hypotheses (see COND_RULES) checked against Revit's exports of the same views."""
import math
import numpy as np
from .reader import ob
from . import gfx

I3 = np.eye(3)


class ViewCtx:
    """what the conditions need to know about the view"""
    def __init__(self, view_dir, detail=2, cut_origin=None, cut_normal=None, kind='plan', scale=100):
        self.dir = np.asarray(view_dir, float); self.dir /= np.linalg.norm(self.dir) or 1
        self.detail = detail or 2
        self.cut_o = None if cut_origin is None else np.asarray(cut_origin, float)
        self.cut_n = None if cut_normal is None else np.asarray(cut_normal, float)
        self.kind = kind; self.scale = scale


def _par(a, b, tol=1e-3):
    return abs(abs(float(np.dot(a, b))) - 1.0) < tol


class Walker:
    def __init__(self, f, ctx, max_depth=4):
        self.f = f; self.ctx = ctx; self.max_depth = max_depth
        self.unknown_conds = {}
        self.annotation_scale = False          # annotation instance transforms already carry the view scale (verified: m_3x3 = 4*I in a 1:4 drafting view)
        self.is_annotation = lambda eid: False
        self.invisible_gs = set()                                       # graphics styles of '<Invisible lines>'
        self.is_2d = lambda eid: self.ctx.kind == 'drafting'          # 2D content (detail items, annotation families): face fills are filled regions

    # ------------------------------------------------------------------ conditions
    def cond_ok(self, c, R, o):
        cls = self.f.tagname(c.get('ptr')); x = c.get('obj') or {}
        comp = x.get('m_comp'); neg = bool(x.get('m_negateDirCondition'))
        ctx = self.ctx
        if cls == 'GConditionInt':
            p = x.get('m_param'); v = x.get('m_value')
            if p == 3:                                   # detail level 1 coarse / 2 medium / 3 fine
                return (ctx.detail == v) if comp == 3 else (ctx.detail != v) if comp == 0 else True
            return True                                  # other int params (selection / highlight states): drawn
        if cls == 'GConditionSelected': return False         # drawn only while the element is selected (camera frusta, grips)
        if cls in ('GConditionDir', 'GConditionCut'):
            d = np.asarray(R, float) @ np.asarray(x['m_dir'], float)      # condition direction in world
            n = np.linalg.norm(d); d = d / n if n else d
            dv = float(np.dot(d, ctx.dir))
            if comp == 10:   r = dv > 1 - 1e-3                             # (?) view direction equals d
            elif comp == 0:
                # (?) view direction perpendicular to d; in 2D family content (drafting views: detail components, symbols) these are the
                # family's reference planes/lines, never shown in the project (2020 Residential 'at grade' vs Revit's export)
                r = abs(dv) < 1e-3
            elif comp == 8:  r = abs(dv) > 1 - 1e-3                        # (?) view direction parallel to d (either sign)
            elif comp in (6, 7):
                cut = self.is_cut(x, d, R, o) if cls == 'GConditionCut' else (ctx.cut_n is not None and _par(d, ctx.cut_n))
                r = cut if comp == 6 else not cut
            else:
                self.unknown_conds[(cls, comp)] = self.unknown_conds.get((cls, comp), 0) + 1; r = True
            return (not r) if neg else r
        self.unknown_conds[(cls, comp)] = self.unknown_conds.get((cls, comp), 0) + 1
        return True

    def is_cut(self, x, d, R, o):
        """GConditionCut: the view's cut plane (normal parallel to d) lies inside [rangeLo, rangeHi] measured along the
        condition direction from the node's local origin"""
        ctx = self.ctx
        if ctx.cut_n is None or not _par(d, ctx.cut_n): return False
        h = float(np.dot(ctx.cut_o - np.asarray(o, float), d))
        return x.get('m_rangeLo', -1e9) - 1e-9 <= h <= x.get('m_rangeHi', 1e9) + 1e-9

    # ------------------------------------------------------------------ walk
    def walk_record(self, eid, R=None, o=None, depth=0, out=None, inherited_gs=None, seen=None):
        out = out if out is not None else {'curves': [], 'solids': [], 'texts': [], 'fills': [], 'instances': []}
        rec = self.f.graphics(eid)
        if not rec or rec.get('class') != 'GElement':
            # no graphics of its own (detail components, annotation symbols): the symbol's graphics through the instance transform
            r = self.f.rec(eid, 'FamilyInstance') if depth == 0 else None
            ii = ob((r or {}).get('fields', {}).get('m_pInstanceInfo')) if r else None
            if ii and ii.get('m_Trf'):
                M = np.asarray(ii['m_Trf']['m_3x3'], float); oo = np.asarray(ii['m_Trf']['m_or'], float)
                if self.annotation_scale and self.is_annotation(eid): M = M * self.ctx.scale
                R0 = I3 if R is None else np.asarray(R, float); o0 = np.zeros(3) if o is None else np.asarray(o, float)
                return self.walk_record(self.f.eid(ii.get('m_symbolId')), R0 @ M, R0 @ oo + o0, depth + 1, out, inherited_gs, seen)
            return out
        R = I3 if R is None else np.asarray(R, float); o = np.zeros(3) if o is None else np.asarray(o, float)
        col = gfx.Collector(self.f); col.handles = {}; col._index(rec['fields'])
        self._col = col
        self.node({'obj': rec['fields'], 'ptr': None}, R, o, depth, out, inherited_gs, eid)
        return out

    def node(self, n, R, o, depth, out, gs, eid):
        n = self._col.deref(n)
        if not isinstance(n, dict): return
        x = n.get('obj')
        if not isinstance(x, dict): return
        cls = self.f.tagname(n.get('ptr')) if n.get('ptr') is not None else 'GElement'
        gi = x.get('m_GInfo') or {}
        g = gi.get('m_categoryId'); g = self.f.eid(g) if g is not None else -1
        if g == -1: g = gs
        conds = x.get('m_oConditions') or []
        if conds and self.is_2d(eid) and any(self.f.tagname(c.get('ptr')) == 'GConditionDir' and (c.get('obj') or {}).get('m_comp') == 0 for c in conds):
            # 2D families: GFilter(dir comp 0) -> GGroup -> 4 x GFilter(comp 10) -> GLine is a reference plane / line, never drawn in a project
            # (2020 Residential section head, break lines, lumber; the visible outlines are filled-region boundaries)
            return
        if conds:
            # conditions of the same kind are alternatives (OR), different kinds must all hold (AND)  (?)
            groups = {}
            for c in conds:
                k = (c.get('ptr'), (c.get('obj') or {}).get('m_comp'), (c.get('obj') or {}).get('m_param'))
                groups.setdefault(k, []).append(c)
            if not all(any(self.cond_ok(c, R, o) for c in g) for g in groups.values()): return
        if cls in ('GElement', 'GFilter', 'GGroup', 'GNode') or (x.get('m_subNodes') is not None and cls not in ('Geometry',)):
            for s in x.get('m_subNodes') or []: self.node(s, R, o, depth, out, g, eid)
            return
        T = lambda pts: (np.asarray(pts, float) @ R.T + o).tolist()
        if cls == 'Geometry':
            faces = [ob(fc) or {} for fc in x.get('m_pFaces') or []]
            if faces and all(fo.get('m_pGFilling') is not None for fo in faces) and (self.is_2d(eid) or self._flat_regions(x, faces, R)):
                # filled region inside a family / detail component: planar faces carrying a fill (pattern, colour, placer)
                self._fills_from_faces(x, faces, R, o, g, eid, out)
                return
            if x.get('m_pFaces'): out['solids'].append({'geo': x, 'R': R, 'o': o, 'gs': g, 'elem': eid, 'flags': gi.get('m_flags')})
            return
        if cls == 'GInstance':
            ii = ob(x.get('m_instanceInfo')) or {}
            t = ii.get('m_Trf') or {}
            sid = self.f.eid(ii.get('m_symbolId'))
            if depth >= self.max_depth or not t: return
            M = np.asarray(t['m_3x3'], float); oo = np.asarray(t['m_or'], float)
            out['instances'].append(sid)
            if self.f.rec(sid, 'FamilyInstance'): return               # nested hosted instances are separate elements
            self.walk_record(sid, R @ M, R @ oo + o, depth + 1, out, g)
            self._col = self._colstack_restore(eid)
            return
        # 2D / curve leaves: reuse the generic collector on this single node
        sub = gfx.Collector(self.f); sub.handles = self._col.handles
        sub.node(n, [], g)
        for p in sub.prims:
            p['elem'] = eid
            if p.get('pts'): p['pts'] = T(p['pts'])
            if p.get('loops'): p['loops'] = [T(l) for l in p['loops'] if l]
            if p['t'] == 'text' and p.get('origin') is not None:
                p['origin'] = T([p['origin']])[0]
                if p.get('x') is not None: p['x'] = (R @ np.asarray(p['x'], float)).tolist()
                if p.get('y') is not None: p['y'] = (R @ np.asarray(p['y'], float)).tolist()
            {'line': out['curves'], 'fill': out['fills'], 'text': out['texts']}.get(p['t'], out['curves']).append(p)

    def _flat_regions(self, geo, faces, R):
        """plan/ceiling/3D-plan symbols: every face of the node carries a fill and lies in a plane parallel to the view plane -> a 2D region
        (masking regions of column and fixture families), not a model solid"""
        if self.ctx.kind not in ('plan',): return False
        try:
            import rvt_brep
            for fc in geo.get('m_pFaces') or []:
                pl = rvt_brep.plane_of((ob(fc) or {}).get('m_pSurf'))
                if not pl: return False
                n = np.cross(np.asarray(pl[1], float), np.asarray(pl[2], float)); n = np.asarray(R, float) @ n
                n = n / (np.linalg.norm(n) or 1)
                if abs(float(n @ np.asarray(self.ctx.dir, float))) < 0.999: return False
            return True
        except Exception: return False

    def _fills_from_faces(self, geo, faces, R, o, g, eid, out):
        try:
            import rvt_brep
            loops_by_h = {fr['handle']: fr['loops'] for fr in rvt_brep.planar_faces(geo)}
        except Exception: return
        # boundary edges: each edge has its own line style (GInfo category = graphics style) and m_flags bit 0 = visible (masking regions and
        # invisible boundaries: 6, drawn boundaries: 7 - 2020 Residential detail components vs Revit's DXF); edge = chord between its end points
        # in the face's (u, v) (interior points not used yet)
        planes = {}
        for fc in geo.get('m_pFaces') or []:
            fo = ob(fc) or {}
            pl = rvt_brep.plane_of(fo.get('m_pSurf')) if fo.get('m_pSurf') else None
            if pl: planes[fc.get('handle')] = pl
        for ed in geo.get('m_pEdges') or []:
            eo = ob(ed) if isinstance(ed, dict) else None
            if not isinstance(eo, dict) or not (eo.get('m_flags') or 0) & 1: continue
            gsid = self.f.eid((eo.get('m_GInfo') or {}).get('m_categoryId'))
            if gsid in (None, -1) or gsid in self.invisible_gs: continue
            refs = [r.get('ref') if isinstance(r, dict) else None for r in eo.get('m_pFace') or []]
            side = next((i for i, r in enumerate(refs) if r in planes), None)
            fl_ = eo.get('m_firstAndLastEdgePnts') or []
            if side is None or len(fl_) < 2: continue
            pl = planes[refs[side]]
            try: pa = rvt_brep.uv3d(pl, *ob(fl_[0])['uv'][side]); pb = rvt_brep.uv3d(pl, *ob(fl_[1])['uv'][side])
            except Exception: continue
            out['curves'].append({'t': 'line', 'pts': (np.asarray([pa, pb], float) @ R.T + o).tolist(), 'gs': gsid, 'elem': eid, 'cond': [], 'boundary': True})
        hs = [fc.get('handle') for fc in geo.get('m_pFaces') or []]
        for h, fo in zip(hs, faces):
            gf = ob(fo.get('m_pGFilling')) or {}
            loops = loops_by_h.get(h)
            if not loops: continue
            T = [(np.asarray(l, float) @ R.T + o).tolist() for l in loops if len(l) > 2]
            pl = gf.get('m_placer') or {}
            out['fills'].append({'t': 'fill', 'loops': T, 'pattern': self.f.eid(gf.get('m_patternId')), 'color': gf.get('m_fillColor'),
                                 'placer': pl, 'R': R.tolist(), 'gs': g, 'elem': eid, 'fill_flags': gf.get('m_flags')})

    def _colstack_restore(self, eid):
        rec = self.f.graphics(eid)
        col = gfx.Collector(self.f); col.handles = {}
        if rec: col._index(rec['fields'])
        return col
