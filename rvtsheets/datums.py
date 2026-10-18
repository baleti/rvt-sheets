"""Grids (plan views, sections) and levels (sections/elevations): datum line from the datum plane (DatumPlane.m_pSurface origin, xVec
along the line, envelope = extents along xVec / yVec), per-view extents from the view's ExtentElem, head symbols (type m_familyTagId)
with their labels at paper size (x view scale). Output prims in view coordinates (model feet)."""
import os
import math
import numpy as np
from .reader import ob, path, INVALID
from . import gfx


def fmt_elev(ft, imperial, f=None):
    if imperial:
        if f is not None and abs(abs(ft) * 12 % 1.0 - 0.0) > 1e-6 and abs(abs(ft) * 12 % 1.0 - 1.0) > 1e-6:       # fractional inches: the project length format (Snowdon level '-3'-5 1/2"')
            try:
                from . import units
                return units.fmt_length(ft, {'m_bUseDefault': 1}, units.length_format(f))
            except Exception: pass
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
            uo_ = self.f.eid(fl.get('m_unplacedOwnerId'))
            if uo_ not in (None, INVALID, -1): continue                       # datum owned by another element (Snowdon Facades duplicate 'L3' levels): not an independent datum, Revit shows one L3
            o = np.asarray(srf['m_origin'], float); x = np.asarray(srf['m_xVec'], float); y = np.asarray(srf['m_yVec'], float)
            env = path(srf, 'm_Envelope', 'm_corners') or [[-50, -50], [50, 50]]
            (a0, b0), (a1, b1) = env
            n = np.cross(x, y)
            # datum line in this view = intersection of the datum plane with the view plane: direction perpendicular to both normals
            dline = np.cross(n, Z)
            if np.linalg.norm(dline) < 1e-6: continue                   # datum plane parallel to the view: not shown
            if v.get('kind') == 'section' and abs(float(n @ Z)) / (np.linalg.norm(n) or 1.0) > 0.05: continue      # sections / elevations show only datum planes perpendicular to the view (Snowdon Structural: the 7.5 degree grid 598948 is absent from Revit's North / Longitudinal DXF, the 82 degree one from East)
            dline /= np.linalg.norm(dline)
            if v.get('kind') == 'section' and (v.get('crop') or {}).get('far_clip_active'):
                # datum planes are finite (envelope): with an active far clip only those that reach the view's depth slab are shown (Snowdon Facades Block 43 elevation:
                # the 'Block 39' levels end 24 ft in front of the 3 ft slab and are not in Revit's picture)
                try:
                    far = float(((v['crop'].get('bounds') or [[0, 0]] * 3)[2])[0]); tol = 0.5
                    cs = np.array([o + x * u + y * w for u in (a0, a1) for w in (b0, b1)])
                    sd = (cs - O) @ Z
                    if sd.max() < -far - tol or sd.min() > tol: continue
                except Exception: pass
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
                if v.get('kind') == 'section':
                    # sections / details: ends t run along the view's up (vertical grids) or right axis from the grid's own origin (P = o + D * t), an unset free
                    # end (0.0) is the 3D free end (Commercial 'Typical Wall Section' grid 1: bubble on top, line down to the crop)
                    Rw = np.asarray(v['right'], float); Uw = np.asarray(v['up'], float)
                    D = Rw if abs(ax @ Rw) > abs(ax @ Uw) else Uw
                    if not f_: f_ = e['m_freeEnd3d']
                    grid_ext = (o + D * b_, o + D * f_)
                else: grid_ext = (o - ax * b_, o - ax * f_)                    # bubble end, free end
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
                if e.get('m_bubbleEnd') and e.get('m_freeEnd') and e.get('m_bubbleEnd3d') and e.get('m_freeEnd3d') and e['m_bubbleEnd'] < e['m_freeEnd'] and e['m_bubbleEnd3d'] > e['m_freeEnd3d']:
                    t_b, t_f = e['m_bubbleEnd3d'], e['m_freeEnd3d']           # 2D ends stored with the head on the left while the 3D ends put it on the right (Snowdon Facades 'Block 37 - Parapet': Revit's head is on the right)
                if t_b or t_f:
                    Xr = Mv[0]
                    lvl_ext = (((o + Xr * t_b - O) @ Mv.T)[:2], ((o + Xr * t_f - O) @ Mv.T)[:2])
                    if not self._meets_crop(v, lvl_ext[0], lvl_ext[1]):
                        # the extents miss the crop region (1:24 detail): the level is still drawn across the crop, head at its right end
                        from .compose import crop_rect_uv
                        cr_ = crop_rect_uv(v)
                        if cr_ is not None:
                            m_ = 0.5 / 12 * (v.get('scale') or 100); vv = lvl_ext[0][1]
                            lvl_ext = (np.array([cr_[2] + m_, vv]), np.array([cr_[0] - m_, vv]))
            if lvl_ext is not None:
                uv_b, uv_f = lvl_ext
                from .compose import crop_rect_uv as _cru
                cr2 = _cru(v)
                if cr2 is not None and cr2[0] <= uv_b[0] <= cr2[2] and not (cr2[0] <= uv_f[0] <= cr2[2]):
                    uv_b, uv_f = uv_f, uv_b          # details: the bubble end lies inside the crop, the free end outside it: the head goes to the end outside (Commercial 1:8 / 1:24 wall details)
                elif cr2 is not None and (uv_b[0] > cr2[2] or uv_b[0] < cr2[0]) and (uv_f[0] > cr2[2] or uv_f[0] < cr2[0]) and abs(uv_b[1] - uv_f[1]) < 1e-6:
                    # both stored ends lie outside the crop (rst basic 'Section Wall': Level 2 -92.6 .. 89 ft in a 36 ft crop): Revit draws the line across the annotation crop region, head at the right end
                    ac3 = self.annotation_rect(v, scale)
                    if ac3 is not None:
                        right = uv_b[0] >= uv_f[0]
                        if not (min(uv_b[0], uv_f[0]) < ac3[0] and max(uv_b[0], uv_f[0]) > ac3[2]): ac3 = None
                    if ac3 is not None:
                        lo3, hi3 = max(min(uv_b[0], uv_f[0]), ac3[0]), min(max(uv_b[0], uv_f[0]), ac3[2])
                        if hi3 > lo3:
                            yy = uv_b[1]; ends = (np.array([hi3, yy]), np.array([lo3, yy]))
                            uv_b, uv_f = (ends if right else ends[::-1])
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
                        ac_ = self.annotation_rect(v, scale)                           # the line spans crop + the annotation offsets (1" each side, active or not: rst basic section 1:50);
                        if ac_ is not None: cr = ac_; m = 0.0                           # the envelope may be shorter (Residential building section, Commercial Mezzanine)
                        lo_, hi_ = max(ua, cr[0] - m), min(ub_, cr[2] + m)         # clipped to the crop + 1/2" (the envelope may be shorter: Commercial Mezzanine)
                        if hi_ <= lo_: lo_, hi_ = cr[0] - m, cr[2] + m                # the envelope misses the crop: Revit still draws the level across it (Commercial Typical Wall Section, Mezzanine)
                        pa, pb = p0 + k * (lo_ - u0), p0 + k * (hi_ - u0)
                        p0, p1 = (pa, pb) if u0 <= ((p1 - O) @ Mv.T)[0] else (pb, pa)
            if r['class'] == 'Level':
                # level line: horizontal in the view at the level elevation; endpoints projected
                pass
            uv0 = ((p0 - O) @ Mv.T)[:2]; uv1 = ((p1 - O) @ Mv.T)[:2]
            if lvl_ext is not None: uv0, uv1 = uv_f, uv_b
            if r['class'] == 'Level' and lvl_ext is None and v.get('kind') == 'section' and uv0[0] > uv1[0]:
                # no stored bubble end: head at the right end (Commercial building section, West elevation levels) unless the datum's origin sits exactly at one envelope end
                # (Commercial Mezzanine, envelope u -45.2 .. 0): the head is there (left end in the North elevation and the wall section, right end in the building section)
                if not (abs(hi) < 1e-6 and abs(lo) > 1e-6 and os.environ.get('RVT_LVLHEAD') != 'right'): uv0, uv1 = uv1, uv0
            if v.get('kind') in ('section', 'plan') and not self._meets_crop(v, uv0, uv1): continue      # outside an active crop: hidden
            if r['class'] == 'Grid' and grid_ext is None and v.get('kind') in ('plan', 'section'):
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
            if r['class'] == 'Level':                      # level line style of the type (LevelAttributes.m_lineAndTextAttr category -> graphic style: 'Center' dash-dot in Revit's Residential / Commercial / rst basic pictures)
                lc = self.f.rec(self.f.eid((tf.get('m_lineAndTextAttr') or {}).get('m_categoryId')))
                gsl = (lc or {}).get('fields', {}).get('m_gstyleIds') or []
                if gsl: st = res.line(self.f.eid(gsl[0]), cid, 'proj', eid, annotation=True)
            cseg = self.f.eid(tf.get('m_categoryForCenterSegment'))
            if cseg not in (None, INVALID):
                st2 = res.line(None, cseg, 'proj', eid, annotation=True)
                st = dict(st, dash=st2.get('dash'))
            prims.append({'t': 'line', 'pts': [uv0.tolist(), uv1.tolist()], 'style': st, 'elem': eid, 'layer': 'datum', 'part': 'line'})
            # heads
            name = fl.get('m_text') or ''
            vals = {'Name': name, 'Elevation': fmt_elev(float(o[2]), imperial, self.f)}
            ends = []
            # bubble at end 1 (envelope low end, verified against Revit's S101 export); per-view ExtentElem m_endBubbleOverrides bit 0 adds end 2
            if grid_ext is not None: pass
            elif r['class'] == 'Grid' and v.get('kind') == 'section' and uv0[1] < uv1[1]:
                uv0, uv1 = uv1, uv0                                  # grids in sections/elevations: the head is at the top end
            # plan grids without per-view extents: east-west lines keep the envelope's low end (p0: Commercial west, rst basic D-H east), north-south lines the
            # north end (Commercial / rst basic lo = north, Snowdon L2 lo = south but Revit's 1-9 are on top)
            if r['class'] == 'Grid' and not e and v.get('kind') == 'plan':
                dv = uv1 - uv0
                if abs(dv[1]) >= abs(dv[0]) and uv0[1] < uv1[1]: uv0, uv1 = uv1, uv0       # north-south lines: bubble at the north end (Commercial, rst basic, Snowdon L2: 1-9 on top)
            ends = [(uv0, uv0 - uv1)]
            if (e.get('m_endBubbleOverrides') or 0) & 1: ends.append((uv1, uv1 - uv0))
            if r['class'] == 'Level': ends = [(uv1, uv1 - uv0)]
            # head leader (ExtentElem.m_pLeader at the bubble end, m_pFreeEndLeader at the free end): the datum line runs end -> elbow -> anchor and the head sits at the anchor
            # (2026 rosetta level 'B.O. Footing': jog before the head)
            for key, bub in (('m_pLeader', True), ('m_pFreeEndLeader', False)):
                ld = ob(e.get(key)) if e.get(key) else None
                if not ld or not ld.get('m_anchor') or not ld.get('m_elbow') or not ld.get('m_end'): continue
                if v.get('kind') not in ('section', 'plan'): continue
                ptw = [np.asarray(ld[k_], float) for k_ in ('m_end', 'm_elbow', 'm_anchor')]
                q = [((p_ - O) @ Mv.T)[:2] for p_ in ptw]
                end_pt = uv1 if (r['class'] == 'Level' or not bub) else uv0
                if not bub: end_pt = uv0 if r['class'] == 'Level' else uv1
                if np.linalg.norm(np.asarray([q[2][0], end_pt[1]]) - end_pt) > 0.05 * max(np.linalg.norm(uv1 - uv0), 1.0) or abs(q[2][0] - end_pt[0]) > 0.05 * max(np.linalg.norm(uv1 - uv0), 1.0): continue        # the anchor is where the bubble end was: leader belongs to the other end / is stale otherwise
                prims[-1]['pts'] = [(uv0 if end_pt is uv1 else uv1).tolist(), q[0].tolist(), q[1].tolist(), q[2].tolist()]
                if bub:
                    dd = q[2] - q[1]
                    ends = [(q[2], dd)] + ([(uv1, uv1 - uv0)] if (e.get('m_endBubbleOverrides') or 0) & 1 and r['class'] != 'Level' else [])
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
                    out.append({'t': 'line', 'pts': [q[:2] for q in pts], 'style': res.line(p.get('gs'), None, 'proj', eid, annotation=True), 'gs': p.get('gs'), 'elem': eid, 'layer': 'datum'})
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
                        'font': font.get('name') or 'Arial', 'halign': ({0: 2, 2: 0}.get(SheetComposer._halign(lab['flags'] or 0), 1) if (level and xd[0] < -0.5) else SheetComposer._halign(lab['flags'] or 0)),
                        'valign': SheetComposer._valign(lab['flags'] or 0), 'anchor': True, 'elem': eid, 'layer': 'text'})      # a head on the left end is mirrored: its text stays upright and reads to the right of the marker
        return out
