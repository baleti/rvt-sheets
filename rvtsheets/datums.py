"""Grids (plan views, sections) and levels (sections/elevations): datum line from the datum plane (DatumPlane.m_pSurface origin, xVec
along the line, envelope = extents along xVec / yVec), per-view extents from the view's ExtentElem, head symbols (type m_familyTagId)
with their labels at paper size (x view scale). Output prims in view coordinates (model feet)."""
import math
import numpy as np
from .reader import ob, path, INVALID
from . import gfx


def fmt_elev(ft, imperial):
    if imperial:
        sgn = '-' if ft < 0 else ''; ft = abs(ft); f = int(ft + 1e-9); inch = round(max(ft - f, 0.0) * 12, 2) + 0.0
        if inch >= 12: f += 1; inch = 0
        i = ('%g' % inch)
        return '%s%d\' - %s"' % (sgn, f, i)
    return '%d' % round(ft * 304.8)


class Datums:
    def __init__(self, drawer):
        self.d = drawer; self.f = drawer.f; self.doc = drawer.doc

    def extents(self, vid):
        out = {}
        for r in self.f.recs('ExtentElem'):
            if self.f.eid(r['fields'].get('m_dbViewId')) != vid: continue
            for e in r['fields'].get('m_idExtents') or []:
                out[self.f.eid(e['first'])] = ob(path(e, 'second', 'm_oExtentData')) or {}
        return out

    @staticmethod
    def _meets_crop(v, uv0, uv1):
        """datum line meets the view's active crop region (2020 Residential 'typ. door head': levels above the 1:8 crop are not in Revit's DXF)"""
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v)
        if cr is None: return True
        from shapely.geometry import LineString, box
        return LineString([tuple(uv0), tuple(uv1)]).intersects(box(*cr))

    @staticmethod
    def annotation_rect(v, scale):
        from .compose import crop_rect_uv
        cr = crop_rect_uv(v)
        if cr is None: return None
        off = (v.get('crop') or {}).get('annotation_offsets') or [0, 0, 0, 0]
        l, r_, t, b = [float(x or 0) * scale for x in off]
        return cr[0] - l, cr[1] - b, cr[2] + r_, cr[3] + t

    @staticmethod
    def _clip(a, b, rc):
        """Liang-Barsky clip of segment a-b to rect (u0, v0, u1, v1); keeps the a->b orientation; None when outside"""
        a = np.asarray(a, float); b = np.asarray(b, float); d = b - a; t0, t1 = 0.0, 1.0
        for p, q in ((-d[0], a[0] - rc[0]), (d[0], rc[2] - a[0]), (-d[1], a[1] - rc[1]), (d[1], rc[3] - a[1])):
            if abs(p) < 1e-12:
                if q < 0: return None
            else:
                t = q / p
                if p < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        if t0 > t1: return None
        return a + d * t0, a + d * t1

    def draw(self, vid, v, elems, O, Mv, scale, res, imperial=False):
        prims = []
        ext = self.extents(vid)
        Z = Mv[2]
        for eid in elems:
            r = self.f.rec(eid, ('Grid', 'Level'))
            if not r: continue
            fl = r['fields']; srf = ob(fl.get('m_pSurface')) or {}
            if not srf.get('m_origin'): continue
            o = np.asarray(srf['m_origin'], float); x = np.asarray(srf['m_xVec'], float); y = np.asarray(srf['m_yVec'], float)
            env = path(srf, 'm_Envelope', 'm_corners') or [[-50, -50], [50, 50]]
            (a0, b0), (a1, b1) = env
            n = np.cross(x, y)
            # datum line in this view = intersection of the datum plane with the view plane: direction perpendicular to both normals
            dline = np.cross(n, Z)
            if np.linalg.norm(dline) < 1e-6: continue                   # datum plane parallel to the view: not shown
            dline /= np.linalg.norm(dline)
            # parameterise along whichever datum axis is the line direction
            if abs(dline @ x) > abs(dline @ y): ax, lo, hi = x, a0, a1
            else: ax, lo, hi = y, b0, b1
            e = ext.get(eid) or {}
            # per-view 2D extents (freeEnd/bubbleEnd) override the 3D extents when set (?)
            grid_ext = None
            if r['class'] == 'Grid' and e.get('m_freeEnd3d') is not None and (e.get('m_freeEnd3d') or e.get('m_bubbleEnd3d')):
                # grid extents are stored along -axis (free = -env hi, bubble = -env lo: Snowdon, Commercial); the view's own 2D ends
                # (m_freeEnd / m_bubbleEnd, set when the view trimmed the datum: Snowdon L2 lettered grids) win over the 3D ends
                f_, b_ = (e.get('m_freeEnd') or 0.0), (e.get('m_bubbleEnd') or 0.0)
                if not (f_ or b_): f_, b_ = e['m_freeEnd3d'], e['m_bubbleEnd3d']
                grid_ext = (o - ax * b_, o - ax * f_)                    # bubble end, free end
                p0, p1 = grid_ext
            elif e.get('m_freeEnd3d') is not None and (e.get('m_freeEnd3d') or e.get('m_bubbleEnd3d')):
                lo, hi = e['m_freeEnd3d'], e['m_bubbleEnd3d']
                p0 = o + ax * lo; p1 = o + ax * hi
            else: p0 = o + ax * lo; p1 = o + ax * hi
            lvl_ext = None
            if r['class'] == 'Level' and v.get('kind') == 'section' and e and (e.get('m_freeEnd3d') is not None):
                # level extents in an elevation/section: ends t along the view's right axis from the level's own origin (P = o + right * t); bubble
                # end = right end, free end 0.0 = unset -> the 3D free end (Commercial: parapet levels have origin x 76.5 and stored ends -161.1/21.2
                # in the building section = Revit's -84.6..97.7, same as the Finished Floor line; north elevation mirrored)
                t_b = e.get('m_bubbleEnd') or e.get('m_bubbleEnd3d') or 0.0
                t_f = e.get('m_freeEnd') or e.get('m_freeEnd3d') or 0.0
                if t_b or t_f:
                    Xr = Mv[0]
                    lvl_ext = (((o + Xr * t_b - O) @ Mv.T)[:2], ((o + Xr * t_f - O) @ Mv.T)[:2])
            if lvl_ext is not None:
                uv_b, uv_f = lvl_ext
                p0 = o; p1 = o          # placeholders: uv set below
            if r['class'] == 'Level' and not e and v.get('kind') == 'section':
                # no per-view extents: Revit draws the level across the crop region plus about 1/2" of paper on each side
                # (2020 Residential building section DXF: 67.97 ft for a 63.59 ft crop at 1:48), head at the +x end
                from .compose import crop_rect_uv
                cr = crop_rect_uv(v)
                if cr:
                    m = 0.5 / 12 * (v.get('scale') or 100)
                    d2 = ((p1 - p0) @ Mv.T)[:2]; L = np.linalg.norm(d2)
                    if L > 1e-9 and abs(d2[1]) < 1e-6 * L:
                        u0 = ((p0 - O) @ Mv.T)[0]; k = (p1 - p0) / ((p1 - O) @ Mv.T - (p0 - O) @ Mv.T)[0]
                        ua, ub_ = sorted([u0, ((p1 - O) @ Mv.T)[0]])
                        lo_, hi_ = max(ua, cr[0] - m), min(ub_, cr[2] + m)         # clipped to the crop + 1/2" (the envelope may be shorter: Commercial Mezzanine)
                        if hi_ > lo_:
                            pa, pb = p0 + k * (lo_ - u0), p0 + k * (hi_ - u0)
                            p0, p1 = (pa, pb) if u0 <= ((p1 - O) @ Mv.T)[0] else (pb, pa)
            if r['class'] == 'Level':
                # level line: horizontal in the view at the level elevation; endpoints projected
                pass
            uv0 = ((p0 - O) @ Mv.T)[:2]; uv1 = ((p1 - O) @ Mv.T)[:2]
            if lvl_ext is not None: uv0, uv1 = uv_f, uv_b
            if r['class'] == 'Level' and lvl_ext is None and v.get('kind') == 'section' and uv0[0] > uv1[0]: uv0, uv1 = uv1, uv0     # no stored bubble end: head at the right end (Commercial building section, Mezzanine)
            if v.get('kind') in ('section', 'plan') and not self._meets_crop(v, uv0, uv1): continue      # outside an active crop: hidden
            if r['class'] == 'Grid' and grid_ext is None and v.get('kind') == 'plan':
                # 3D-extent grid in a cropped view: drawn to the annotation crop region (crop + offsets x scale), the bubble moves there
                # (Snowdon L2: vertical grids end 8 ft outside the crop at 1:96, bubbles at the new ends)
                ac = self.annotation_rect(v, scale)
                if ac:
                    seg = self._clip(uv0, uv1, ac)
                    if seg is None: continue
                    uv0, uv1 = seg
            cid = self.d.vis.info.info.get(eid, {}).get('cat', -2000220)
            st = res.line(None, cid, 'proj', eid, annotation=True)
            t = self.f.rec(self.f.eid(fl.get('m_attrId'))) or {'fields': {}}
            tf = t['fields']
            cseg = self.f.eid(tf.get('m_categoryForCenterSegment'))
            if cseg not in (None, INVALID):
                st2 = res.line(None, cseg, 'proj', eid, annotation=True)
                st = dict(st, dash=st2.get('dash'))
            prims.append({'t': 'line', 'pts': [uv0.tolist(), uv1.tolist()], 'style': st, 'elem': eid, 'layer': 'datum', 'part': 'line'})
            # heads
            name = fl.get('m_text') or ''
            vals = {'Name': name, 'Elevation': fmt_elev(float(o[2]), imperial)}
            ends = []
            # bubble at end 1 (envelope low end, verified against Revit's S101 export); per-view ExtentElem m_endBubbleOverrides bit 0 adds end 2
            if grid_ext is not None: pass
            elif r['class'] == 'Grid' and v.get('kind') == 'section' and uv0[1] < uv1[1]:
                uv0, uv1 = uv1, uv0                                  # grids in sections/elevations: the head is at the top end
            elif r['class'] == 'Grid' and not e and v.get('kind') == 'plan':
                # no per-view extent: default bubble at the north end of N-S lines and the west end of E-W lines (Revit's export of the
                # writer's GA/GB grids and Commercial grid 2 / lettered grids; with extents the stored ends decide, as before)
                dv = uv1 - uv0
                if abs(dv[1]) >= abs(dv[0]):
                    if uv0[1] < uv1[1]: uv0, uv1 = uv1, uv0
                elif uv0[0] > uv1[0]: uv0, uv1 = uv1, uv0
            ends = [(uv0, uv0 - uv1)]
            if (e.get('m_endBubbleOverrides') or 0) & 1: ends.append((uv1, uv1 - uv0))
            if r['class'] == 'Level': ends = [(uv1, uv1 - uv0)]
            sym = self.f.eid(tf.get('m_familyTagId'))
            gb = (self.f.g.res.get(sym) or {}).get('bbox') if sym not in (None, INVALID) else None
            rad = float(gb[1][1]) if gb else 0.0                 # grid head symbol: circle centred on its origin, radius = bbox max y
            for pt, d in ends:
                if sym in (None, INVALID): continue
                d = d / (np.linalg.norm(d) or 1)
                if r['class'] == 'Grid': pt = pt + d * rad * scale         # the line ends on the bubble's edge (Revit S101 export)
                # head family: +x along the outward line direction for levels, +y outward for grids (?)
                if r['class'] == 'Grid': R = np.array([[d[1], d[0], 0], [-d[0], d[1], 0], [0, 0, 1]]).T * 0 + np.array([[-d[1], d[0], 0], [d[0], d[1], 0], [0, 0, 1]]).T
                else: R = np.array([[d[0], -d[1], 0], [d[1], d[0], 0], [0, 0, 1]])
                prims += self.head(sym, R * scale, np.array([pt[0], pt[1], 0.0]), vals, eid, res, scale, level=r['class'] == 'Level')
        return prims

    def head(self, sid, R, o, vals, eid, res, scale, level=False):
        out = []
        g = self.f.graphics(sid)
        if g and g.get('class') == 'GElement':
            col = gfx.Collector(self.f); coll = col.collect(g)
            for p in coll:
                if p['t'] == 'line' and p.get('gs') not in (None, -1) and self.d.drawable_gs(p['gs']):     # not the family's reference lines
                    pts = gfx.transform_pts(p['pts'], R, o)
                    out.append({'t': 'line', 'pts': [q[:2] for q in pts], 'style': res.line(p.get('gs'), None, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'datum'})
                elif p['t'] == 'fill' and p.get('loops') and p.get('gs') not in (None, -1) and self.d.drawable_gs(p['gs']):      # filled quadrants of the level head
                    out.append({'t': 'fill', 'loops': [[q[:2] for q in gfx.transform_pts(l, R, o)] for l in p['loops']], 'color': p.get('color') or [0, 0, 0], 'elem': eid, 'layer': 'datum'})
            if level and not any(p['t'] == 'fill' for p in coll) and any(p['t'] == 'line' and p.get('gs') in (None, -1) for p in coll):
                # level head circle: cross through the centre and two black quadrants (NW, SE) - Revit's 'Level Head - Circle' (2020 Residential elevations);
                # the cross lines are the family's style-less lines, the fills are not stored in the symbol graphics
                circ = [p for p in coll if p['t'] == 'line' and p.get('gs') not in (None, -1) and len(p['pts']) > 8]
                if circ:
                    P = np.asarray([q[:2] for p in circ for q in p['pts']], float)
                    c0 = (P.min(0) + P.max(0)) / 2; rad = (P.max(0) - P.min(0)).max() / 2
                    st = res.line(circ[0].get('gs'), None, 'proj', eid, annotation=True)
                    for a, b in (((-rad, 0), (rad, 0)), ((0, -rad), (0, rad))):
                        pts = gfx.transform_pts([[c0[0] + a[0], c0[1] + a[1], 0.0], [c0[0] + b[0], c0[1] + b[1], 0.0]], R, o)
                        out.append({'t': 'line', 'pts': [q[:2] for q in pts], 'style': st, 'elem': eid, 'layer': 'datum'})
                    for a0, a1 in ((90, 180), (270, 360)):
                        th = np.radians(np.linspace(a0, a1, 13))
                        loop = [[c0[0], c0[1], 0.0]] + [[c0[0] + rad * np.cos(t), c0[1] + rad * np.sin(t), 0.0] for t in th] + [[c0[0], c0[1], 0.0]]
                        out.append({'t': 'fill', 'loops': [[q[:2] for q in gfx.transform_pts(loop, R, o)]], 'color': [0, 0, 0], 'elem': eid, 'layer': 'datum'})
        sym = self.d.dec.titleblock_symbol(sid)
        from .sheet import SheetComposer
        for lab in (sym or {}).get('labels', []):
            txt = ' '.join(str(vals.get(prm.get('name'), prm.get('sample') or '')) for prm in lab.get('params') or [])
            tt = self.doc['text_types'].get(lab['type']) or {}
            font = self.doc['fonts'].get(tt.get('font')) or {}
            org = gfx.transform_pts([lab['origin']], R, o)[0]
            xd = (np.asarray(R, float) @ np.asarray(lab['base'], float))[:2]
            out.append({'t': 'text', 'text': txt, 'origin': org[:2], 'x': [1.0, 0.0], 'size': (font.get('size') or 0.0078) * scale,
                        'font': font.get('name') or 'Arial', 'halign': SheetComposer._halign(lab['flags'] or 0), 'valign': SheetComposer._valign(lab['flags'] or 0), 'anchor': True,
                        'elem': eid, 'layer': 'text'})
        return out
