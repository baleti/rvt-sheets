"""Stage 5: annotations generated from their records (Revit stores no graphics for them).
Linear dimensions (LinearDimString): references' points (m_refPnts) projected on the dimension line (m_pDimLine origin + direction),
witness lines (gap / extension), tick marks (LeaderStyle of the dimension type), segment texts at m_ArrSegInfo[i].m_origin.
Sizes are paper sizes (feet of paper) x view scale. Defaults where the type does not store a value are Revit's out-of-the-box
type values (?): witness gap 1/16", extension 3/32", tick 3/64" diagonal, text offset 1/32"."""
import math
import os
import numpy as np
from .reader import ob, path, INVALID
from . import units

IN = 1 / 12.0


def typ_params(a, tf):
    return ob(tf.get('m_pParamValueSetElementId')) or {}


def f_isarea(tags, tr):
    return tags.f.eid(tr['fields'].get('m_areaSchemeId')) not in (None, INVALID, -1)


def _area_of_scheme_region(drawer, area_rec):
    """area (square feet) of an Area element: the region of its area scheme's boundary lines (CurveElem category -2000079, m_areaSchemeId) that
    contains the Area's point (Residential area plan: 1310 SF)"""
    try:
        from shapely.geometry import Point
        from shapely.ops import unary_union, polygonize
        from shapely.geometry import LineString
        f = drawer.f; sch = f.eid(area_rec['fields'].get('m_areaSchemeId'))
        c = getattr(drawer, '_area_cache', None)
        if c is None: c = drawer._area_cache = {}
        if sch not in c:
            segs = []
            for e, i in drawer.vis.info.info.items():
                if i['cls'] != 'CurveElem' or i['cat'] != -2000079: continue
                r = f.rec(e)
                if f.eid(r['fields'].get('m_areaSchemeId')) != sch: continue
                cr = ob(path(ob(r['fields'].get('m_pCurveDriver')) or {}, 'm_pCrv')) or {}
                o = np.asarray(cr.get('m_origin') or [], float); d = np.asarray(cr.get('m_dirVec') or [], float); ep = cr.get('m_endParams')
                if len(o) < 2 or len(d) < 2 or not ep: continue
                segs.append(LineString([tuple(np.round((o + d * ep[0])[:2], 5)), tuple(np.round((o + d * ep[1])[:2], 5))]))
            c[sch] = list(polygonize(unary_union(segs))) if segs else []
        pt = area_rec['fields'].get('m_point')
        if not pt: return None
        P = Point(pt[0], pt[1])
        for poly in c[sch]:
            if poly.contains(P): return float(poly.area)
    except Exception: return None
    return None


def _property_line_value(tr, pid):
    """property line segment tag labels: -1012616 bearing (degrees, minutes, seconds from the N/S axis), -1012614 distance (decimal feet, 2 places),
    -1012615 N/S, -1012617 E/W (quadrant bearing of the curve direction; Commercial site plan: N 0 59 39 W 242.80')"""
    try:
        c = ob(tr['fields'].get('m_curve')) or {}
        d = np.asarray(c.get('m_dirVec'), float); ep = c.get('m_endParams') or [0.0, 0.0]
        if pid == -1012614: return "%.2f'" % abs(float(ep[1]) - float(ep[0]))
        if pid == -1012615: return 'N' if d[1] >= -1e-9 else 'S'
        if pid == -1012617: return 'E' if d[0] >= 0 else 'W'
        if pid == -1012616:
            deg = math.degrees(math.atan2(abs(d[0]), abs(d[1])))
            sec = int(round(deg * 3600)); return "%d\u00b0 %02d' %02d\"" % (sec // 3600, sec % 3600 // 60, sec % 60)
    except Exception: return None
    return None


def label_str(v):
    """text of a label parameter value: an ElementId value (decoded EID) prints nothing (invalid -1) -- never its repr"""
    if v is None: return ''
    if isinstance(v, bool): return str(v)
    r = type(v).__name__
    if r == 'EID' or repr(v).startswith('EID('):
        return ''
    return str(v)


DIM_TXT_OFF = 0.0 if os.environ.get('RVT_TEXTBASE', '1') == '1' else 0.3      # dimension text sits on the dimension line: its bottom-aligned baseline is the descent above (Revit PDF: baseline 0.227 em above the line)


class Annotations:
    def __init__(self, drawer):
        self.d = drawer; self.f = drawer.f; self.doc = drawer.doc
        self.proj_len = units.length_format(self.f)

    def spot_slope(self, eid, O, Mv, scale, res):
        """spot slope shown as a triangle (SpotElevation with m_oTypeState.m_slopeRep 1; 2020 Residential south elevation vs Revit's DXF):
        hypotenuse = m_horizLeaderLength of paper starting at the reference point + m_bendOrPosPtOffset (model) and running downhill along the
        slope, horizontal leg from that point, vertical leg at its far end; rise text (12" run) outside the vertical leg, run text '1'-0"'
        centred above the horizontal leg"""
        r = self.f.rec(eid, 'SpotElevation')
        if not r: return []
        fl = r['fields']; ts = ob(fl.get('m_oTypeState')) or {}
        if ts.get('m_slopeRep') != 1 or not fl.get('m_refPnts') or not ts.get('m_slopeDir'): return []
        A = np.asarray(fl['m_refPnts'][0], float) + np.asarray(fl.get('m_bendOrPosPtOffset') or [0, 0, 0], float)
        a = ((A - O) @ Mv.T)[:2]; sd = (Mv @ np.asarray(ts['m_slopeDir'], float))[:2]
        if abs(sd[0]) < 1e-9: return []
        k = abs(sd[1] / sd[0]); H = float(fl.get('m_horizLeaderLength') or 1 / 12) * scale
        run = H / math.sqrt(1 + k * k); rise = run * k; dx = -1.0 if sd[0] > 0 else 1.0       # the triangle lies downhill of the anchor
        b = a + [dx * run, 0.0]; c = b + [0.0, -rise]
        line = res.line(None, -2000260, 'proj', eid, annotation=True)
        out = [{'t': 'line', 'pts': [a.tolist(), b.tolist(), c.tolist(), a.tolist()], 'style': line, 'elem': eid, 'layer': 'annotation'}]
        typ = self.f.rec(self.f.eid(fl.get('m_styleSymbolId')))
        tf = typ['fields'] if typ else {}
        la = ob(tf.get('m_pLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        size = (font.get('size') or 3 / 32 * IN) * scale
        opt = dict(ob(tf.get('m_oLinFormatOptions')) or {}, m_bSuppressSpaces=1)      # Revit's export: '1'-0"'
        rtxt = units.fmt_length(k, opt, self.proj_len); ctxt = units.fmt_length(1.0, opt, self.proj_len)
        gap = 1 / 16 * IN * scale
        out.append({'t': 'text', 'text': rtxt, 'origin': [b[0] + dx * gap, (b[1] + c[1]) / 2], 'x': [1.0, 0.0], 'size': size, 'font': font.get('name') or 'Arial',
                    'halign': 0 if dx > 0 else 2, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
        out.append({'t': 'text', 'text': ctxt, 'origin': [(a[0] + b[0]) / 2, a[1] + 1.5 * gap], 'x': [1.0, 0.0], 'size': size, 'font': font.get('name') or 'Arial',
                    'halign': 1, 'valign': 2, 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out

    def contour_labels(self, eid, O, Mv, scale, res, crop=None):
        """topography contour labels (ContourLabelingElem): one text per m_textPos (x, y, elevation) along the contour, rotated with m_textDir (kept
        readable), the elevation in the labelling attribute's format and font (Commercial site: '1' - 0"' at 1/16" Arial)"""
        r = self.f.rec(eid, 'ContourLabelingElem')
        if not r: return []
        ud = ob(path(r['fields'], 'm_data', 'm_oUserData')) or {}
        pos = ud.get('m_textPos') or []; dirs = ud.get('m_textDir') or []
        at = self.f.rec(self.f.eid(r['fields'].get('m_attrId')))
        af = at['fields'] if at else {}
        la = ob(af.get('m_lineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        size = (font.get('size') or 1 / 16 * IN) * scale
        opt = ob(af.get('m_pFormatOptions')) or {'m_bUseDefault': 1}
        out = []
        for k, p_ in enumerate(pos):
            a = ((np.asarray(p_, float) * [1, 1, 0] - O) @ Mv.T)[:2]
            if crop is not None and not (crop[0] <= a[0] <= crop[2] and crop[1] <= a[1] <= crop[3]): continue       # labels beyond the crop region are not in Revit's view (Commercial site: 3 of 4)
            d = (Mv @ np.asarray(dirs[k] if k < len(dirs) else [1, 0, 0], float))[:2]
            ang = math.atan2(d[1], d[0])
            if abs(ang) > math.pi / 2: ang += math.pi
            txt = units.fmt_length(float(p_[2]), opt, self.proj_len)
            out.append({'t': 'text', 'text': txt, 'origin': a.tolist(), 'x': [math.cos(ang), math.sin(ang)], 'size': size, 'font': font.get('name') or 'Arial',
                        'halign': 1, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out

    def spot_coordinate(self, eid, fl, tf, O, Mv, scale, res):
        """spot coordinate (dimension style type 5): filled arrow at the reference point, leader a -> bend (m_bendOrPosPtOffset) -> end (+ m_horizLeaderLength),
        the type's target symbol (circle + cross + underline) at the leader end, text 'N <north>' / 'E <east>' above it (values m_values[2] / [1] of the
        first segment, the style's length format); layout read off the rst basic Level 2 DXF (leader end E: text left 0.5 in, top 0.34 in of paper from E)"""
        P = np.asarray(fl['m_refPnts'][0], float); a = ((P - O) @ Mv.T)[:2]
        off = np.asarray(fl.get('m_bendOrPosPtOffset') or [0, 0, 0], float)
        b = a + (Mv @ off)[:2]; dx = 1.0 if b[0] >= a[0] else -1.0
        hl = float(fl.get('m_horizLeaderLength') or 0.0); c = b + [dx * hl, 0.0]
        line = res.line(None, -2000260, 'proj', eid, annotation=True)
        out = [{'t': 'line', 'pts': [a.tolist(), b.tolist(), c.tolist()], 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'leader'}]
        # arrowhead of the type's leader style (filled): length = style size, full angle = style angle
        ang, size = 15 * math.pi / 180, 1 / 16 * IN
        ls = self.f.rec(self.f.eid(tf.get('m_arrowHeadStyleId')))
        if ls:
            for x in path(ls['fields'], 'm_pParamValueSetDouble', 'm_paramSet') or []:
                if x.get('m_paramId') == 4293960870: ang = x['m_value']
                elif x.get('m_paramId') == 4293960882: size = x['m_value']
        u = (b - a); u = u / (np.linalg.norm(u) or 1.0); n = np.array([-u[1], u[0]])
        L = size * scale; w = L * math.tan(ang / 2)
        out.append({'t': 'fill', 'loops': [[a.tolist(), (a + u * L + n * w).tolist(), (a + u * L - n * w).tolist(), a.tolist()]], 'color': [0, 0, 0], 'elem': eid, 'layer': 'annotation_fill', 'part': 'arrow'})
        sym = None
        for x in path(typ_params(self, tf), 'm_paramSet') or []:
            if x.get('m_paramId') == 4293960860: sym = self.f.eid(x.get('m_value'))
        if sym not in (None, INVALID, -1):
            out += symbol_prims(self.d, sym, np.eye(3) * scale, np.array([c[0], c[1], 0.0]), eid, res, -2000260)
        la = ob(tf.get('m_pLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        fs = (font.get('size') or 3 / 32 * IN) * scale
        seg = ob((fl.get('m_ArrSegInfo') or [None])[0]) or {}
        vals = [(q.get('m_value') if isinstance(q, dict) else None) for q in seg.get('m_values') or []]
        opt = ob(tf.get('m_oLinFormatOptions')) or {}
        lines = []
        if len(vals) >= 3 and vals[2] is not None: lines.append('%s %s' % (tf.get('m_seIndNS') or 'N', units.fmt_length(float(vals[2]), opt, self.proj_len)))
        if len(vals) >= 2 and vals[1] is not None: lines.append('%s %s' % (tf.get('m_seIndEW') or 'E', units.fmt_length(float(vals[1]), opt, self.proj_len)))
        if lines:
            out.append({'t': 'text', 'text': '\n'.join(lines), 'origin': [c[0] - 0.5 * IN * scale if dx > 0 else c[0] + 0.5 * IN * scale, c[1] + 0.34 * IN * scale], 'x': [1.0, 0.0], 'size': fs,
                        'font': font.get('name') or 'Arial', 'halign': 0 if dx > 0 else 2, 'valign': 0, 'anchor': True, 'elem': eid, 'layer': 'text', 'part': 'text'})
        return out

    def _spot_z(self, fl, P):
        """elevation shown by a spot elevation on a picked element: the stored point sits on the element's bounding box top, Revit reads the face under
        the point (Snowdon L2 beams: 7'-4 1/2" where the stored z says 7'-7"; sloped beams in L1: -4'-3 1/2" at mid span of a beam whose box top is -3'-5 1/2"):
        z of the highest non-vertical face triangle covering the point (plane interpolation), within 1.5 ft of the stored z"""
        try:
            pn = fl.get('m_planeNormal')
            if pn is not None and abs(float(pn[2])) < 0.9: return float(P[2])        # spots in elevations / sections read vertical faces: keep the stored value
            pk = ((ob(fl.get('m_pPick')) or {}).get('m_elemPicks') or [None])[0]
            e = self.f.eid((ob(pk) or {}).get('m_elemId')) if pk else None
            if e in (None, INVALID, -1): return float(P[2])
            import rvt_elemmesh as E
            T = np.asarray(E.element_mesh(self.f.g, e).get('tris') or [], float).reshape(-1, 3, 3)
            if not len(T): return float(P[2])
            n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(n, axis=1) + 1e-12
            flat = np.abs(n[:, 2]) / nl > 0.5
            T = T[flat]; n = n[flat]
            if not len(T): return float(P[2])
            a, b, c = T[:, 0, :2], T[:, 1, :2], T[:, 2, :2]; q = np.asarray(P[:2], float)
            d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
            ok = np.abs(d) > 1e-12; d = np.where(ok, d, 1.0)
            l1 = ((b[:, 1] - c[:, 1]) * (q[0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (q[1] - c[:, 1])) / d
            l2 = ((c[:, 1] - a[:, 1]) * (q[0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (q[1] - c[:, 1])) / d
            l3 = 1 - l1 - l2
            hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
            if not hit.any():                                                  # point beside the faces (coped beam end): the beam's own top level near the stored z
                zs = T[:, :, 2].max(1); zs = zs[np.abs(zs - P[2]) <= 1.0]
                return float(zs.max()) if len(zs) else float(P[2])
            z = l1 * T[:, 0, 2] + l2 * T[:, 1, 2] + l3 * T[:, 2, 2]
            z = z[hit]; z = z[np.abs(z - P[2]) <= 1.5]
            return float(z.max()) if len(z) else float(P[2])
        except Exception:
            import os
            if os.environ.get('RVTSHEETS_DEBUG'): raise
            return float(P[2])

    def spot_elevation(self, eid, O, Mv, scale, res):
        """spot elevation in plans/sections (draft, no Revit reference yet): target symbol (circle + cross) at the reference point, leader to
        the bend point (m_bendOrPosPtOffset, model units), shoulder (style m_leaderShoulderLength, paper) and the elevation text (reference z
        formatted with the style's length options) beside the shoulder end"""
        r = self.f.rec(eid, 'SpotElevation')
        if not r: return []
        fl = r['fields']; ts = ob(fl.get('m_oTypeState')) or {}
        typ_ = self.f.rec(self.f.eid(fl.get('m_styleSymbolId')))
        if typ_ and typ_['fields'].get('m_dimensionStyleType') == 5 and fl.get('m_refPnts'): return self.spot_coordinate(eid, fl, typ_['fields'], O, Mv, scale, res)
        if ts.get('m_slopeRep') == 1 or not fl.get('m_refPnts') or not fl.get('m_displayElevation'): return []
        P = np.asarray(fl['m_refPnts'][0], float)
        a = ((P - O) @ Mv.T)[:2]
        typ = self.f.rec(self.f.eid(fl.get('m_styleSymbolId')))
        tf = typ['fields'] if typ else {}
        la = ob(tf.get('m_pLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        size = (font.get('size') or 3 / 32 * IN) * scale
        seg = ob((fl.get('m_ArrSegInfo') or [None])[0]) or {}
        if not fl.get('m_leader') and seg.get('m_offset') is not None:
            # no leader (Snowdon 'Beam Elevation (Project)'): Revit draws the bare text at the dimension origin + the segment's text offset, parallel to
            # the picked beam (rotated 90 degrees on beams running along the view's y axis); no target symbol
            off = np.asarray(seg['m_offset'] + [0.0] * (3 - len(seg['m_offset'])), float)
            b = a + (Mv @ off)[:2]
            ang = 0.0
            pk = ((ob(fl.get('m_pPick')) or {}).get('m_elemPicks') or [None])[0]
            bb = self.d.vis.info.bbox(self.f.eid((ob(pk) or {}).get('m_elemId'))) if pk else None
            if bb is not None:
                ext = np.abs((Mv @ (np.asarray(bb[1], float) - np.asarray(bb[0], float)))[:2])
                if ext[1] > ext[0] * 1.5: ang = math.pi / 2
            opt = ob(tf.get('m_oLinFormatOptions')) or {}
            txt = units.fmt_length(self._spot_z(fl, P), opt, self.proj_len)
            return [{'t': 'text', 'text': txt, 'origin': b.tolist(), 'x': [math.cos(ang), math.sin(ang)], 'size': size, 'font': font.get('name') or 'Arial',
                     'halign': 1, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'}]
        off = np.asarray(fl.get('m_bendOrPosPtOffset') or [0, 0, 0], float)
        b = a + (Mv @ off)[:2] if fl.get('m_leaderLine') else a
        sh = float(tf.get('m_leaderShoulderLength') or 0) * (scale if scale else 1)
        dx = 1.0 if (b[0] >= a[0]) else -1.0
        c = b + [dx * sh, 0.0]
        line = res.line(None, -2000260, 'proj', eid, annotation=True)
        rad = 1.0 / 304.8 * scale * 1.5            # 1.5 paper mm
        t = np.linspace(0, 2 * np.pi, 25)
        out = [{'t': 'line', 'pts': (a + rad * np.stack([np.cos(t), np.sin(t)], 1)).tolist(), 'style': line, 'elem': eid, 'layer': 'annotation'},
               {'t': 'line', 'pts': [(a - [rad, 0]).tolist(), (a + [rad, 0]).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation'},
               {'t': 'line', 'pts': [(a - [0, rad]).tolist(), (a + [0, rad]).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation'}]
        if fl.get('m_leaderLine'): out.append({'t': 'line', 'pts': [a.tolist(), b.tolist(), c.tolist()], 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'leader'})
        opt = ob(tf.get('m_oLinFormatOptions')) or {}
        txt = units.fmt_length(self._spot_z(fl, P), opt, self.proj_len)
        gap = 1 / 16 * IN * scale
        out.append({'t': 'text', 'text': txt, 'origin': [c[0] + dx * gap, c[1]], 'x': [1.0, 0.0], 'size': size, 'font': font.get('name') or 'Arial',
                    'halign': 0 if dx > 0 else 2, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out

    def angular_dimension(self, eid, O, Mv, scale, res):
        """angular dimension (AngularDim): the arc through m_origin about the centre of m_pDimArc between the directions of the two reference points, a filled 15 degree
        arrowhead (3 mm of paper) plus a radial tick of the same length at each arc end (pointing out of the arc), the value in degrees (style m_oAngFormatOptions) centred
        1.13 text heights outside the arc midpoint (Snowdon L1_43_High 7.5 degrees vs Revit's DXF dimension block)"""
        r = self.f.rec(eid, 'AngularDim')
        if not r: return []
        fl = r['fields']
        arc = ob(fl.get('m_pDimArc')) or {}
        refs = fl.get('m_refPnts') or []
        if not arc.get('m_center') or len(refs) < 2 or not fl.get('m_origin'): return []
        wr = fl.get('m_witnessRefs') or []
        vs = getattr(self.d, '_vis_elems', None)
        if vs is not None:
            for w in wr:
                e_ = self.f.eid(((ob(ob(w).get('m_pWitnessRef') or {}) or {}).get('m_geomRef') or {}).get('m_elemId'))
                if e_ not in (None, INVALID, -1) and e_ not in vs and self.f.rec(e_): return []
        P = lambda p: ((np.asarray(p, float) - O) @ Mv.T)[:2]
        c = P(arc['m_center']); rad = float(np.linalg.norm(P(fl['m_origin']) - c))
        if rad < 1e-6: return []
        a1, a2 = (math.atan2(*(P(q) - c)[::-1]) for q in refs[:2])
        d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi          # the short way round
        typ = self.f.rec(self.f.eid(fl.get('m_styleSymbolId')))
        tf = typ['fields'] if typ else {}
        la = ob(tf.get('m_pLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        size = (font.get('size') or 3 / 32 * IN) * scale
        line = res.line(None, -2000260, 'proj', eid, annotation=True)
        pt = lambda a: c + rad * np.array([math.cos(a), math.sin(a)])
        angs = a1 + d * np.linspace(0, 1, max(8, int(abs(d) * 60)))
        out = [{'t': 'line', 'pts': [pt(a).tolist() for a in angs], 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'line'}]
        L = 0.003 * 3.28084 * scale * (1.0 if not units.is_imperial(self.f) else 1.0)         # 3 mm of paper
        half = L * math.tan(math.radians(7.5))
        for a, sgn in ((a1, 1.0), (a1 + d, -1.0)):
            tip = pt(a); tang = np.array([-math.sin(a), math.cos(a)]) * (1 if d > 0 else -1) * sgn      # towards the other end
            rd = np.array([math.cos(a), math.sin(a)]); base = tip + tang * L
            tri = [tip.tolist(), (base + rd * half).tolist(), (base - rd * half).tolist(), tip.tolist()]
            out.append({'t': 'fill', 'loops': [tri], 'color': [0, 0, 0], 'elem': eid, 'layer': 'annotation_fill', 'part': 'arrow'})
            out.append({'t': 'line', 'pts': tri, 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'arrow'})
            out.append({'t': 'line', 'pts': [(tip - rd * L / 2).tolist(), (tip + rd * L / 2).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'arrow'})
        seg = (fl.get('m_ArrSegInfo') or [{}])[0]; vals = seg.get('m_values') or [{}]
        val = vals[0].get('m_value')
        if val is None or val < 0: val = abs(d)
        deg = val * 180 / math.pi
        ao = ob(tf.get('m_oAngFormatOptions')) or {}
        acc = ao.get('m_accuracy') or 1.0
        if acc < 1e-6: txt = ('%.4f' % deg).rstrip('0').rstrip('.')
        else: txt = ('%.*f' % (max(0, -int(math.floor(math.log10(acc)))), round(deg / acc) * acc)).rstrip('0').rstrip('.') if acc < 1 else '%d' % round(deg / acc * acc)
        txt += '\u00b0'
        am = a1 + d / 2; rdm = np.array([math.cos(am), math.sin(am)])
        tg = np.array([-rdm[1], rdm[0]])
        if tg[0] < -1e-9 or (abs(tg[0]) < 1e-9 and tg[1] < 0): tg = -tg
        out.append({'t': 'text', 'text': txt, 'origin': (pt(am) + rdm * size * 1.13).tolist(), 'x': tg.tolist(), 'size': size, 'font': font.get('name') or 'Arial',
                    'bold': bool(la.get('m_bBold')), 'italic': bool(la.get('m_bItalic')), 'halign': 1, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out

    def dimension(self, eid, O, Mv, scale, res):
        r = self.f.rec(eid, 'LinearDimString')
        if not r: return []
        fl = r['fields']
        wr = fl.get('m_witnessRefs') or []
        if wr and all(self.f.eid(((ob(ob(w).get('m_pWitnessRef') or {}) or {}).get('m_geomRef') or {}).get('m_elemId')) in (None, INVALID, -1) for w in wr):
            return []            # every witness reference points at no element (Snowdon L2 dimension 595385): Revit does not draw it
        vs = getattr(self.d, '_vis_elems', None)
        if vs is not None:           # Revit omits a dimension when a referenced element is not in the view (Snowdon L2 38'-7" dim: its wall 587033 lies outside the view volume)
            for w in wr:
                e_ = self.f.eid(((ob(ob(w).get('m_pWitnessRef') or {}) or {}).get('m_geomRef') or {}).get('m_elemId'))
                if e_ not in (None, INVALID, -1) and e_ not in vs and self.f.rec(e_) and (getattr(self.d, '_vis_why', {}) or {}).get(e_, 'outside_view_volume') == 'outside_view_volume':      # only references outside the view volume drop a dimension (Residential basement dim 235357: its wall lies above the cut, Revit still lists the dimension)
                    self.d.stats['dim_hidden_ref'] += 1; return []
        dl = ob(fl.get('m_pDimLine')) or {}
        if not dl.get('m_origin'): return []
        vv_ = self.d.doc['views'].get(getattr(self.d, '_cur_vid', None)) or {}
        rg_ = vv_.get('range') or {}
        if vv_.get('kind') == 'plan' and rg_.get('bottom') is not None and rg_.get('top') is not None and dl['m_origin'][2] < rg_['bottom'] - 0.5 and os.environ.get('RVT_DIMZ', '1') == '1':
            self.d.stats['dim_below_range'] += 1; return []      # a dimension whose plane lies below the plan's view range (Residential first floor dim 382006 at z -8: not in Revit's collector)
        P = lambda p: ((np.asarray(p, float) - O) @ Mv.T)[:2]
        o = P(dl['m_origin']); d = (Mv @ np.asarray(dl['m_dirVec'], float))[:2]
        if np.linalg.norm(d) < 1e-9: return []
        d /= np.linalg.norm(d); n = np.array([-d[1], d[0]])
        refs = [P(p) for p in fl.get('m_refPnts') or []]
        if len(refs) < 2: return []
        ts = [float((p - o) @ d) for p in refs]
        st = self.doc['text_types']
        typ = self.f.rec(self.f.eid(fl.get('m_styleSymbolId')))
        tf = typ['fields'] if typ else {}
        la = ob(tf.get('m_pLineAndTextAttr')) or {}
        font = self.doc['fonts'].get(self.f.eid(la.get('m_fontId'))) or {}
        size = (font.get('size') or 3 / 32 * IN) * scale
        cat = -2000260
        line = res.line(None, cat, 'proj', eid, annotation=True)
        tickst = res.line(None, self.f.eid(tf.get('m_tickCategoryId')) if tf.get('m_tickCategoryId') is not None else cat, 'proj', eid, annotation=True)
        gap = 1 / 16 * IN * scale; ext = 3 / 32 * IN * scale; tick = 3 / 64 * IN * scale
        lsn = self.f.rec(self.f.eid(tf.get('m_arrowHeadStyleId')))
        if lsn:
            nm = path(lsn['fields'], 'm_symbolInfo', 'm_name') or ''
            import re
            m = re.search(r'(\d+)/(\d+)"', nm)
            if m: tick = int(m.group(1)) / int(m.group(2)) * IN * scale
        out = []
        t0, t1 = min(ts), max(ts)
        out.append({'t': 'line', 'pts': [(o + d * t0).tolist(), (o + d * t1).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'line'})
        # references to family instances (window/door centre planes) take the type's centerline tick mark ('Dot Open 1/16"') instead of the linear tick
        wr = fl.get('m_witnessRefs') or []
        cen = set()
        if len(wr) == len(refs):
            for i_, w_ in enumerate(wr):
                try:
                    g_ = ob(w_['m_pWitnessRef'])['m_geomRef']; r_ = self.f.rec(self.f.eid(g_['m_elemId']))
                    if r_ and r_['class'] == 'FamilyInstance': cen.add(i_)
                except Exception: pass
        cdia = 1 / 16 * IN * scale
        cst = self.f.rec(self.f.eid(tf.get('m_centerlineTickMarkStyleId')))
        if cst:
            import re as _re
            m_ = _re.search(r'(\d+)/(\d+)"', path(cst['fields'], 'm_symbolInfo', 'm_name') or '')
            if m_: cdia = int(m_.group(1)) / int(m_.group(2)) * IN * scale
        for i_, (p, t) in enumerate(zip(refs, ts)):
            q = o + d * t                       # foot on the dimension line
            v = q - p; L = np.linalg.norm(v)
            gap_i = gap
            if len(wr) == len(refs) and os.environ.get('RVT_WGAP', '1') == '1':
                g_ = wr[i_].get('m_gapToElt') if isinstance(wr[i_], dict) else None      # each witness reference stores its own gap (paper feet): windows / doors 0.027-0.030 vs 0.0052 for walls (Residential plan 32: Revit's witness lines start ~1 ft farther at 1:48)
                if isinstance(g_, (int, float)) and 0 < g_ < 0.2: gap_i = g_ * scale
            if L > gap_i:
                u = v / L
                out.append({'t': 'line', 'pts': [(p + u * gap_i).tolist(), (q + u * ext).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation', 'part': 'witness'})
            if i_ in cen:
                th = np.linspace(0, 2 * math.pi, 25)
                out.append({'t': 'line', 'pts': [(q + (d * math.cos(x) + n * math.sin(x)) * cdia / 2).tolist() for x in th], 'style': dict(tickst, w=line['w']), 'elem': eid, 'layer': 'annotation', 'part': 'arrow'})
                continue
            a = (d + n) / math.sqrt(2) * tick / 2
            out.append({'t': 'line', 'pts': [(q - a).tolist(), (q + a).tolist()], 'style': dict(tickst, w=max(tickst['w'], line['w'] * 2)), 'elem': eid, 'layer': 'annotation', 'part': 'arrow'})
        # segment texts
        segs = fl.get('m_ArrSegInfo') or []
        order = np.argsort(ts)
        ang = math.atan2(d[1], d[0])
        if ang > math.pi / 2 + 1e-6 or ang <= -math.pi / 2 + 1e-6: d_txt = -d
        else: d_txt = d
        for i, sg in enumerate(segs):
            if i + 1 >= len(ts): break
            val = None
            vals = sg.get('m_values') or []
            if vals and vals[0].get('m_value', -1) >= 0: val = vals[0]['m_value']
            if val is None: val = abs(ts[i + 1] - ts[i])
            txt = units.fmt_length(val, ob(tf.get('m_oLinFormatOptions')) or {}, self.proj_len)
            eq = bool((fl.get('m_flags') or 0) & 0x80) and len(ts) > 2          # equality display (flag 0x80 of the dimension): every segment reads 'EQ' (rst basic cross section roof dimension)
            if eq: txt = tf.get('m_equalityText') or 'EQ'
            org = sg.get('m_origin')
            pos = P(org) if org and any(org) else o + d * (ts[i] + ts[i + 1]) / 2
            out.append({'t': 'text', 'text': txt, 'origin': (pos + np.array([-d_txt[1], d_txt[0]]) * size * DIM_TXT_OFF).tolist(), 'x': d_txt.tolist(), 'size': size,
                        'font': font.get('name') or 'Arial', 'bold': bool(la.get('m_bBold')), 'italic': bool(la.get('m_bItalic')), 'halign': 1, 'valign': 2, 'anchor': True, 'elem': eid, 'layer': 'text'})
            if not eq and tf.get('m_alternateUnits') == 2:                  # alternate units below the primary text (rst basic 3000 / 9' - 10": 2.27 ft = 2.91 text heights at 1:100)
                aopt = ob(tf.get('m_oLinFormatOptionsAlternate')) or {}
                if (aopt.get('m_accuracy') or 1) < 1e-6 and units.du_of(aopt) in (0, 1, 2, 3, 6):      # unrestricted accuracy (Snowdon '_Working' styles: '236.5' under 19'-8 1/2"): all decimals, trailing zeros dropped, no unit symbol
                    k_ = {0: 0.3048, 1: 30.48, 2: 304.8, 3: 1.0, 6: 12.0}[units.du_of(aopt)]
                    am = ('%.4f' % (val * k_)).rstrip('0').rstrip('.')
                else: am = units.fmt_length(val, aopt, self.proj_len)
                atxt = (tf.get('m_alternateUnitsPrefix') or '') + am + (tf.get('m_alternateUnitsSuffix') or '')
                out.append({'t': 'text', 'text': atxt, 'origin': (pos + np.array([-d_txt[1], d_txt[0]]) * size * (DIM_TXT_OFF - (1.73 if (aopt.get('m_accuracy') or 1) < 1e-6 else 2.91))).tolist(), 'x': d_txt.tolist(), 'size': size,
                            'font': font.get('name') or 'Arial', 'bold': bool(la.get('m_bBold')), 'italic': bool(la.get('m_bItalic')), 'halign': 1, 'valign': 2, 'anchor': True, 'elem': eid, 'layer': 'text', 'part': 'alt_text'})
        if not segs:
            txt = units.fmt_length(t1 - t0, ob(tf.get('m_oLinFormatOptions')) or {}, self.proj_len)
            pos = o + d * (t0 + t1) / 2
            out.append({'t': 'text', 'text': txt, 'origin': (pos + np.array([-d_txt[1], d_txt[0]]) * size * DIM_TXT_OFF).tolist(), 'x': d_txt.tolist(), 'size': size,
                        'font': font.get('name') or 'Arial', 'bold': bool(la.get('m_bBold')), 'italic': bool(la.get('m_bItalic')), 'halign': 1, 'valign': 2, 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out


class Tags:
    """IndependentTag / RoomTag / SpaceTag / AreaTag: tag family symbol (saved graphics + labels) at the head position, paper size x scale,
    labels filled with the tagged element's parameter values (instance, then type)."""
    def __init__(self, drawer):
        self.d = drawer; self.f = drawer.f; self.doc = drawer.doc

    def params_of(self, eid):
        p = (self.d.fe.params().get(eid) or {}).get('params') or {}
        return p

    def symbol_params(self, sym, depth=0):
        """type parameters by built-in id, following derived symbols to their master type (m_masterId; c4-geometry's finding,
        rvt_params.symbol_params does the same plus family captions but scans every record per call - too slow per tag)"""
        c = self.__dict__.setdefault('_symp', {})
        if sym in c: return c[sym]
        out = self.raw_params(sym)
        r = self.f.rec(sym)
        if r:
            # built-in type parameters stored as family parameters under the unsigned 32-bit id (door Width -1001301 = 4293965995, Height -1001300)
            for k, v in self.fam_values(r).items():
                k = int(k)
                if k >= 2 ** 31 and isinstance(v, (int, float, str)) and v != '': out.setdefault(k - 2 ** 32, v)
        mid = self.f.eid(r['fields'].get('m_masterId')) if r else None
        if mid not in (None, INVALID, sym) and depth < 3:
            for k, v in self.symbol_params(mid, depth + 1).items(): out.setdefault(k, v)
        c[sym] = out
        return out

    def fam_values(self, rec, key='m_pParams'):
        """family parameter values {family param element id: value} from m_pParams / m_pInstParams entries"""
        out = {}
        for e in (ob(rec['fields'].get(key)) or {}).get('m_params') or []:
            pid = e.get('m_paramId')
            if not isinstance(pid, int): continue
            if e.get('m_str'): v = e['m_str']
            elif e.get('m_elemId') not in (None, 4294967295, -1) and isinstance(e.get('m_elemId'), int): v = e['m_elemId']
            elif e.get('m_value'): v = e['m_value']
            elif e.get('m_int'): v = e['m_int']
            else: v = ''
            out[pid] = v
        return out

    def instance_labels(self, eid, O, Mv):
        """labels of an annotation family instance (generic annotations, keynote symbols): symbol labels placed with the instance
        transform; values from the instance's m_pInstParams over the symbol's m_pParams (family params, by id) and built-in params"""
        from . import gfx
        from .sheet import SheetComposer
        r = self.f.rec(eid)
        if not r: return []
        ii = ob(r['fields'].get('m_pInstanceInfo')) or {}
        sid = self.f.eid(ii.get('m_symbolId')); trf = ii.get('m_Trf') or {}
        if sid in (None, INVALID) or not trf.get('m_3x3'): return []
        sym = self.d.dec.titleblock_symbol(sid)
        if not sym or not sym.get('labels'): return []
        vals = {}
        chain = [sid]; srec = self.f.rec(sid)
        while srec and len(chain) < 4:
            m = self.f.eid(srec['fields'].get('m_masterId'))
            if m in (None, INVALID) or m in chain: break
            chain.append(m); srec = self.f.rec(m)
        for c in reversed(chain):
            cr = self.f.rec(c)
            if cr: vals.update(self.fam_values(cr))
        vals.update({k: v for k, v in self.fam_values(r, 'm_pInstParams').items() if v != '' or k not in vals})
        for k, v in self.symbol_params(sid).items(): vals.setdefault(k, v)
        for k, v in self.raw_params(eid).items(): vals[k] = v
        M = np.asarray(trf['m_3x3'], float); o = np.asarray(trf.get('m_or') or [0, 0, 0], float)
        k = float(np.linalg.norm(M[:, 0])) or 1.0
        out = []
        for lab in sym['labels']:
            parts = []
            for prm in lab.get('params') or []:
                v = vals.get(prm.get('param'))
                if v is None: v = ''
                if isinstance(v, float): v = '%g' % v
                parts.append((prm.get('prefix') or '') + label_str(v) + (prm.get('suffix') or ''))
            txt = ' '.join(parts).strip()
            if not txt: continue
            tt = self.doc['text_types'].get(lab['type']) or {}
            font = self.doc['fonts'].get(tt.get('font')) or {}
            pw = gfx.transform_pts([lab['origin']], M, o)[0]
            org = ((np.asarray(pw, float) - O) @ Mv.T)[:2]
            xd = (Mv @ (M @ np.asarray(lab.get('base') or [1, 0, 0], float)))[:2]
            if np.linalg.norm(xd) < 1e-9: xd = np.array([1.0, 0.0])
            if xd[0] < -1e-6: xd = -xd                                    # mirrored instances keep readable text
            out.append({'t': 'text', 'text': txt, 'origin': org.tolist(), 'x': (xd / np.linalg.norm(xd)).tolist(), 'size': (font.get('size') or 0.0078) * k,
                        'font': font.get('name') or 'Arial', 'bold': tt.get('bold'), 'halign': SheetComposer._halign(lab['flags'] or 0),
                        'valign': SheetComposer._valign(lab['flags'] or 0), 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out

    def element_props(self, eid):
        """properties for picking (control API): name, typeName, familyName, levelName, hostId (tagged element), params {name: value}; every key optional"""
        out = {}
        r = self.f.rec(eid)
        if not r: return out
        fl = r['fields']
        ii = ob(fl.get('m_pInstanceInfo')) or {}
        sym = self.f.eid(ii.get('m_symbolId')) if ii else self.f.eid(fl.get('m_symbolId'))
        if sym not in (None, INVALID, -1):
            tn = self.type_name(sym)
            if tn: out['typeName'] = tn
            sr = self.f.rec(sym)
            fam = self.f.rec(self.f.eid(sr['fields'].get('m_familyId'))) if sr else None
            fn = (ob((fam or {}).get('fields', {}).get('m_symbolInfo')) or {}).get('m_name') if fam else None
            if fn: out['familyName'] = fn
        lv = self.f.rec(self.f.eid(fl.get('m_assocLevelId'))) if fl.get('m_assocLevelId') not in (None, INVALID) else None
        if lv and lv['fields'].get('m_text'): out['levelName'] = lv['fields']['m_text']
        for k in ('m_taggedElementId', 'm_taggedRoomElemId'):
            h = self.f.eid(path(fl, k, 'm_linkInstOrHostId'))
            if h not in (None, INVALID, -1): out['hostId'] = h
        if fl.get('m_text'): out['name'] = fl['m_text']
        try:
            prm = {}
            for k, v in (self.params_of(eid) or {}).items():
                if isinstance(v, (int, float, str)) and v != '': prm[str(k)] = v
            if prm: out['params'] = prm
        except Exception: pass
        return out

    def type_name(self, sym, depth=0):
        r = self.f.rec(sym)
        if not r: return ''
        n = (ob(r['fields'].get('m_symbolInfo')) or {}).get('m_name') or ''
        if n or depth > 3: return n
        mid = self.f.eid(r['fields'].get('m_masterId'))
        return self.type_name(mid, depth + 1) if mid not in (None, INVALID, sym) else ''

    def raw_params(self, eid):
        """{built-in param id (negative int): value} straight from the element's m_pParamValueSet* (the named reader params
        mislabel some ids, e.g. room Name/Number/Comments; reported in NEEDS-FROM-READER.md)"""
        out = {}
        r = self.f.rec(eid)
        if not r: return out
        for k in ('m_pParamValueSetAString', 'm_pParamValueSetDouble', 'm_pParamValueSetInt', 'm_pParamValueSetElementId'):
            o = ob(r['fields'].get(k)) or {}
            for e in o.get('m_paramSet') or []:
                pid = e.get('m_paramId')
                if isinstance(pid, int):
                    if pid >= 2 ** 31: pid -= 2 ** 32
                    out[pid] = e.get('m_value')
        return out

    def tag(self, eid, O, Mv, scale, res):
        from . import gfx
        from .sheet import SheetComposer
        r = self.f.rec(eid, ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol', 'RoomTag', 'SpaceTag', 'AreaTag'))
        if not r: return []
        fl = r['fields']
        sid = self.f.eid(fl.get('m_symbolId'))
        if r['class'] in ('SpanDirectionSymbol', 'BeamSystemTag') and os.environ.get('RVT_ACTUAL_SYM', '1') == '1':
            sa_ = self.f.eid(fl.get('m_actualSymbolId'))          # the instance's own symbol copy: its geometry has the Left / Right / Top / Bottom parameters applied (Snowdon Parking 582085: arrows 90 ft long)
            if sa_ not in (None, INVALID, -1) and self.f.rec(sa_): sid = sa_
        if r['class'] in ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol'):
            pos = fl.get('m_absHeadPos'); tagged = self.f.eid(path(fl, 'm_taggedElementId', 'm_linkInstOrHostId'))
            if pos is None:
                # 2026 layout (writer test file): head in m_oTagOrientationCell, tagged element in the first reference of the cell list
                pos = (ob(fl.get('m_oTagOrientationCell')) or {}).get('m_headLocation')
                for c in (ob(fl.get('m_cellList')) or {}).get('m_cells') or []:
                    refs = (ob(c) or {}).get('m_references') or []
                    if refs:
                        tagged = self.f.eid(path(ob(refs[0]) or {}, 'm_referenceIdKey', 'm_hostOrLinkElemId', 'm_linkInstOrHostId')); break
            if tagged in (None, INVALID, -1):
                # 2024 layout (Snowdon): tagged entities cell
                for te in (ob(fl.get('m_taggedEntitiesCell')) or {}).get('m_taggedEntities') or []:
                    t_ = self.f.eid(path(ob(te) or {}, 'm_taggedId', 'm_linkInstOrHostId'))
                    if t_ not in (None, INVALID, -1): tagged = t_; break
        else:
            pos = fl.get('m_point'); tagged = self.f.eid(path(fl, 'm_taggedRoomElemId', 'm_linkInstOrHostId'))
            if pos is None: pos = (ob(fl.get('m_oTagOrientationCell')) or {}).get('m_headLocation')      # 2024 layout (Snowdon area tags)
            off = fl.get('m_tagOffset')
            if off and pos: pos = (np.asarray(pos, float) + np.asarray(off, float)).tolist()
        if pos is None: return []
        vs = getattr(self.d, '_vis_elems', None)
        if r['class'] in ('IndependentTag', 'BeamSystemTag') and vs is not None and tagged not in (None, INVALID, -1) and tagged not in vs and self.f.rec(tagged):
            self.d.stats['tag_hidden_host'] += 1; return []           # the tagged element is not shown in this view (outside the range / crop volume, hidden)
        vals = dict(self.params_of(tagged)); raw = self.raw_params(tagged)
        # type parameters of the tagged element (Type Mark, Type Name...)
        tr = self.f.rec(tagged); tsym = None
        if tr:
            ii = ob(tr['fields'].get('m_pInstanceInfo')) or {}
            sym = self.f.eid(ii.get('m_symbolId')) if ii else None
            if sym in (None, INVALID):                         # system families (walls, floors...): the type element sits in an '...AttributesId' field
                import re as _re
                for k_, v_ in tr['fields'].items():
                    if _re.fullmatch(r'm_\w*Attr(ibutes)?Id', k_) and v_ is not None and self.f.eid(v_) not in (None, INVALID, -1) and self.f.rec(self.f.eid(v_)): sym = self.f.eid(v_); break
            tsym = sym
            if sym not in (None, INVALID):
                for k, v in self.params_of(sym).items(): vals.setdefault(k, v)
                for k, v in self.symbol_params(sym).items(): raw.setdefault(k, v)
        o = ((np.asarray(pos, float) - O) @ Mv.T)
        R = np.eye(3) * scale
        ang = 0.0
        if r['class'] in ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol'):
            oc = ob(fl.get('m_oTagOrientationCell')) or {'m_orientation': fl.get('m_orientation'), 'm_rotationAngle': fl.get('m_rotationAngle')}      # 2020 layout: orientation on the element
            # tag orientation: 0 horizontal, 1 vertical, 2 model (rotation angle): Snowdon L2 column tags at 45 deg, beam tags at 90 deg
            if oc.get('m_orientation') == 1: ang = math.pi / 2
            elif oc.get('m_orientation') == 2: ang = float(oc.get('m_rotationAngle') or 0.0)
            if ang:
                ca, sa = math.cos(ang), math.sin(ang)
                R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]]) * scale
        if tr and tr['class'] == 'PropertyLineSegment':       # property line tags run along their segment, flipped to read left to right / bottom to top (Commercial site DXF: -89, 0, 88, -2 degrees)
            try:
                dv = (Mv @ np.asarray((ob(tr['fields'].get('m_curve')) or {}).get('m_dirVec'), float))[:2]
                ang = math.atan2(dv[1], dv[0])
                while ang > math.pi / 2 + 1e-6: ang -= math.pi
                while ang <= -math.pi / 2 + 1e-6: ang += math.pi
                ca, sa = math.cos(ang), math.sin(ang); R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]]) * scale
            except Exception: pass
        out = []
        g = self.f.graphics(sid)
        if g and g.get('class') == 'GElement':
            col = gfx.Collector(self.f)
            coll = col.collect(g)
            lines_ = [p for p in coll if p['t'] == 'line']
            sp_ = self.params_of(sid)
            frame = False
            if r['class'] in ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol') and len(lines_) == 4 and len(coll) == 4 and any(sp_.get(k) for k in ('Left', 'Right', 'Top', 'Bottom')):
                # 'Structural Framing Tag' (Left/Right/Top/Bottom text margins): its only geometry is the label frame rectangle; Revit's sheets show the bare text
                xs = sorted({round(q[0], 5) for p in lines_ for q in p['pts']}); ys = sorted({round(q[1], 5) for p in lines_ for q in p['pts']})
                frame = len(xs) == 2 and len(ys) == 2
            if r['class'] == 'SpanDirectionSymbol' and os.environ.get('RVT_SPAN_TAGS', '1') == '1':
                # the 8 lines tagged 11..18 (flags 0xE0 set) are the family's margin marks (Left/Right/Top/Bottom bounds): Revit's DXF shows only the arrows
                coll = [p for p in coll if not (p['t'] == 'line' and p.get('tag') not in (None, 0xFFFFFFFF) and 11 <= p['tag'] <= 18)]
            for p in coll:
                if p['t'] == 'line' and not frame:
                    pts = gfx.transform_pts(p['pts'], R, o)
                    out.append({'t': 'line', 'pts': [q[:2] for q in pts], 'style': (dict(res.line(p.get('gs'), None, 'proj', eid, annotation=True), rgb=[0, 0, 0]) if r['class'] == 'SpanDirectionSymbol' else res.line(p.get('gs'), None, 'proj', eid, annotation=True)), 'gs': p.get('gs'), 'elem': eid, 'layer': 'annotation'})
                elif p['t'] == 'fill' and p.get('loops'):
                    out.append({'t': 'fill', 'loops': [[q[:2] for q in gfx.transform_pts(l, R, o)] for l in p['loops']], 'color': p.get('color'), 'elem': eid, 'layer': 'symbolic_fill'})
                elif p['t'] == 'text' and p.get('text') and p.get('origin') is not None:
                    # static family text (door tag 'x' between width and height): paper size x scale, rotated with the tag
                    q = dict(p); q['origin'] = gfx.transform_pts([p['origin']], R, o)[0][:2]
                    M_ = np.asarray(R, float) / scale
                    q['x'] = (M_ @ np.asarray(p['x'] or [1, 0, 0], float))[:2].tolist()
                    q['y'] = (M_ @ np.asarray(p['y'] or [0, 1, 0], float))[:2].tolist() if p.get('y') else None
                    q['size'] = (p.get('size') or 0.0078) * scale
                    for k_ in ('box', 'text_box', 'text_off'):
                        if q.get(k_): q[k_] = [a_ * scale for a_ in q[k_]]
                    q.update(elem=eid, layer='text')
                    out.append(q)
        sym = self.d.dec.titleblock_symbol(sid)
        anchor = None
        try:                                                   # model-space point the tag annotates: centre of the tagged element's box
            bb = self.d.vis.info.bbox(tagged) if tagged not in (None, INVALID, -1) else None
            if bb is not None: anchor = ((np.asarray(bb[0], float) + np.asarray(bb[1], float)) / 2).tolist()
        except Exception: anchor = None
        for lab in (sym or {}).get('labels', []):
            parts = []; seps = []
            for prm in lab.get('params') or []:
                nm = prm.get('name') or ''
                v = raw.get(prm.get('param')) if isinstance(prm.get('param'), int) and prm.get('param') < 0 else None
                if v is None: v = vals.get(nm)
                if prm.get('param') == -1002001 and not v and tsym not in (None, INVALID): v = self.type_name(tsym)       # Type Name: the (master) symbol's own name
                if v is None and nm == 'Area' and tr and tr['class'] == 'RoomElem' and f_isarea(self, tr) and os.environ.get('RVTSHEETS_AREA_POLY'): v = _area_of_scheme_region(self.d, tr)      # off by default: polygon of the boundary lines gives 1277 SF where Revit prints 1310 (Residential area plan)
                if v is None and nm == 'Area' and tr and tr['class'] == 'RoomElem':      # room area: Revit computes it from the boundary; here the floor face of the room volume
                    try:
                        import rvt_elemmesh as E
                        T_ = np.asarray(E.element_mesh(self.f.g, tagged).get('tris') or [], float).reshape(-1, 3, 3)
                        if len(T_):
                            fl_ = T_[(np.abs(T_[:, :, 2] - T_[:, :, 2].min()) < 1e-3).all(1)]
                            if len(fl_): v = float(sum(np.linalg.norm(np.cross(t_[1] - t_[0], t_[2] - t_[0])) / 2 for t_ in fl_))
                    except Exception: v = None
                if v is None and tr and tr['class'] == 'PropertyLineSegment' and isinstance(prm.get('param'), int):
                    v = _property_line_value(tr, prm['param'])                     # bearing / distance / N-S / E-W of the segment (Commercial site plan)
                if v is None and nm == 'Default Thickness': v = vals.get('Foundation Thickness')           # floor type default thickness (stored under that name)
                if v is None and nm == 'Elevation at Top' and tr and tr['class'] == 'Floor':               # floor top = level elevation + height offset (Snowdon span direction symbols 'TOS(5'-6")')
                    lv = vals.get('Level'); le = self.params_of(lv).get('Elevation') if isinstance(lv, int) else None
                    if isinstance(le, (int, float)): v = float(le) + float(vals.get('Height Offset From Level') or 0.0)
                if isinstance(v, int) and not isinstance(v, bool) and v > 0 and 'Type' in nm and self.f.rec(v):
                    try: v = self.type_name(v) or v                       # ElementId-valued type parameter (JoistSystem 'Beam Type' = the beam type element: '18LH04')
                    except Exception: pass
                if v is None: v = ''                                   # Revit shows an empty label when the value is missing (sample text only in the family editor)
                if isinstance(v, float) and prm.get('fmt'):
                    v = units.fmt_length(v, dict(prm['fmt'], m_displayUnits=units.du_of(prm['fmt'])), units.length_format(self.f))      # the label's own number format (CW12")
                    if (ob(prm['fmt'].get('m_symbolTypeId') if isinstance(prm['fmt'].get('m_symbolTypeId'), dict) else {}) or {}).get('m_typeId', '') == '': pass
                if isinstance(v, float):
                    if any(w in nm for w in ('Length', 'Width', 'Height', 'Elevation', 'Offset', 'Thickness', 'Depth', 'Perimeter')): v = units.fmt_length(v, {'m_bUseDefault': 1}, units.length_format(self.f))
                    elif 'Area' in nm: v = ('{:,} SF'.format(int(round(v)))) if units.is_imperial(self.f) else ('%.2f m²' % (v * 0.09290304))
                    else: v = '%g' % v
                parts.append((prm.get('prefix') or '') + label_str(v) + (prm.get('suffix') or ''))
                seps.append('\n' if prm.get('linebreak') else ' ' * int(prm.get('spaces') if prm.get('spaces') is not None else 1))
            tt = self.doc['text_types'].get(lab['type']) or {}
            font = self.doc['fonts'].get(tt.get('font')) or {}
            org = gfx.transform_pts([lab['origin']], R, o)[0]
            txt_ = ''.join((seps[k_] if k_ else '') + pt_ for k_, pt_ in enumerate(parts))      # separators between label parameters: line break or the stored number of spaces (Snowdon CW12\")
            if lab.get('width') and not lab.get('nowrap') and txt_:           # label width (paper): Revit wraps the label text at it (rst basic beam tags: '... CHS-Circular / Hollow / Sections ...')
                from .viewdraw import wrap_text
                txt_ = wrap_text(txt_, lab['width'] * scale, (font.get('size') or 0.0078) * scale / 0.72, font.get('name') or 'Arial', bool(tt.get('bold')))
            out.append({'t': 'text', 'text': txt_, 'origin': org[:2], 'x': [math.cos(ang), math.sin(ang)], 'size': (font.get('size') or 0.0078) * scale,
                        'font': font.get('name') or 'Arial', 'bold': tt.get('bold'), 'halign': SheetComposer._halign(lab['flags'] or 0), 'valign': SheetComposer._valign(lab['flags'] or 0),
                        'anchor': True, 'elem': eid, 'layer': 'text'})
        if r['class'] in ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol') and fl.get('m_leader') and anchor is not None:
            # leader (2020 layout): straight line from the head to the tagged element's centre (rst basic section tags: vertical leaders down to the joist / beam)
            exact_ = False
            try:
                end = ((np.asarray(anchor, float) + np.asarray(fl.get('m_endOffset') or [0, 0, 0], float) - O) @ Mv.T)[:2]
                bb_ = self.d.vis.info.bbox(tagged)
                if bb_ is not None:                              # long thin elements (joists, beams): the leader meets the element straight below / beside the head
                    cs_ = np.asarray([((np.asarray([x_, y_, z_], float) - O) @ Mv.T)[:2] for x_ in (bb_[0][0], bb_[1][0]) for y_ in (bb_[0][1], bb_[1][1]) for z_ in (bb_[0][2], bb_[1][2])])
                    lo_, hi_ = cs_.min(0), cs_.max(0); wd_, ht_ = hi_ - lo_
                    if wd_ > 2 * ht_: end = np.array([min(max(o[0], lo_[0]), hi_[0]), (lo_[1] + hi_[1]) / 2])
                    elif ht_ > 2 * wd_:
                        end = np.array([(lo_[0] + hi_[0]) / 2, min(max(o[1], lo_[1]), hi_[1])])
                        if (self.d.vis.info.info.get(tagged) or {}).get('cat') in (-2001330, -2000100) and not np.any(fl.get('m_endOffset') or [0]): end = np.array([(lo_[0] + hi_[0]) / 2, hi_[1]]); exact_ = True      # columns: the leader meets the top of the column (rst basic detail 1253612: Revit target at the parapet level)
                cat_ = self.d.vis.info.info.get(eid, {}).get('cat')
                start = o[:2]; pts_ = None
                tp_ = next((q for q in reversed(out) if q.get('t') == 'text' and q.get('text') and q.get('layer') == 'text'), None)
                if tp_ is not None and abs(math.sin(ang)) < 1e-6 and os.environ.get('RVT_SHELF', '1') == '1':
                    # elbow leader (rst basic detail 1253612 vs Revit's DXF): a horizontal shelf at the vertical middle of the label block, from the block edge facing
                    # the target (shelf length ~ 8.8 mm of paper), then a straight line to the target
                    from .viewdraw import _font
                    sz_ = float(tp_['size']); em_ = sz_ / 0.72; lines_ = tp_['text'].split('\n'); n_ = len(lines_)
                    fo_ = _font(tp_.get('font') or 'Arial', bool(tp_.get('bold')))
                    wd_l = [(fo_.getlength(l_) / 200.0 * em_) if fo_ else len(l_) * 0.5 * em_ for l_ in lines_]
                    W_ = max(wd_l); ox_, oy_ = tp_['origin'][:2]; ha_ = tp_.get('halign') or 0
                    xl_ = {0: ox_, 1: ox_ - W_ / 2, 2: ox_ - W_}[ha_]; xr_ = xl_ + W_
                    H_ = (n_ - 1) * em_ * 1.22 + 0.9 * em_
                    yc_ = {0: oy_ - H_ / 2, 1: oy_, 2: oy_ + H_ / 2}[tp_.get('valign') or 0]
                    side_ = 1.0 if end[0] > (xl_ + xr_) / 2 else -1.0
                    sx_ = xr_ if side_ > 0 else xl_
                    ex_ = sx_ + side_ * 0.0290 * scale
                    eo_ = fl.get('m_elbowOffset')
                    if eo_ is not None and not fl.get('m_bLeaderIsStraight') and pos is not None:
                        eb_ = (((np.asarray(pos, float) + np.asarray(eo_, float)) - O) @ Mv.T)[:2]          # the elbow stored in the tag: head + m_elbowOffset (world feet)
                        if abs(eb_[1] - o[1]) < 1e-3 * max(scale, 1): ex_ = float(eb_[0]); side_ = 1.0 if ex_ > o[0] else -1.0; sx_ = xr_ if side_ > 0 else xl_
                    start = np.array([sx_, yc_]); pts_ = [start.tolist(), [ex_, yc_], end.tolist()]
                if np.linalg.norm(end - o[:2]) > 1e-6:
                    out.append({'t': 'line', 'pts': pts_ or [o[:2].tolist(), end.tolist()], 'style': res.line(None, cat_, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation', 'part': 'leader', '_tagged': None if exact_ else tagged})
            except Exception: pass
        if anchor is not None:
            for p_ in out: p_['anchor'] = anchor; p_['host'] = tagged       # anchor: world feet (a text prim's old boolean 'anchor' is replaced; both truthy)
        return out


class Markers:
    """elevation markers (InteriorElev): body symbol of the type (InteriorElevAttributes.m_elevationSymbolId) at m_pos, paper size x scale,
    one filled arrowhead per arrow (InteriorElevArrow: look direction = its crop basis z) drawn by Revit, apex angle 2 x m_ahAngleDouble,
    tangent to the circle of diameter m_width (?)"""
    def __init__(self, drawer):
        self.d = drawer; self.f = drawer.f; self.doc = drawer.doc

    def elevation(self, eid, O, Mv, scale, res):
        from . import gfx
        r = self.f.rec(eid, 'InteriorElev')
        if not r: return []
        fl = r['fields']; pos = fl.get('m_pos')
        if pos is None: return []
        vt = self.f.rec(self.f.eid(fl.get('m_symbolId')))
        at = self.f.rec(self.f.eid(vt['fields'].get('m_elevatnAttrId'))) if vt else None
        af = at['fields'] if at else {}
        c = ((np.asarray(pos, float) - O) @ Mv.T)
        out = []; st = res.line(None, -2000535, 'proj', eid, annotation=True)
        sym = self.f.eid(af.get('m_elevationSymbolId'))
        g = self.f.graphics(sym) if sym not in (None, INVALID) else None
        R = np.eye(3) * scale
        if g and g.get('class') == 'GElement':
            for p in gfx.Collector(self.f).collect(g):
                if p['t'] == 'line' and p.get('gs') not in (None, -1) and self.d.drawable_gs(p['gs']): out.append({'t': 'line', 'pts': [q[:2] for q in gfx.transform_pts(p['pts'], R, c)], 'style': res.line(p.get('gs'), -2000535, 'proj', eid, annotation=True), 'gs': p.get('gs'), 'elem': eid, 'layer': 'annotation'})
        rad = (af.get('m_width') or 0.041) / 2 * scale; half = af.get('m_ahAngleDouble') or math.pi / 4
        if not out:
            out.append({'t': 'line', 'pts': [(c[:2] + rad * np.array([math.cos(t), math.sin(t)])).tolist() for t in np.linspace(0, 2 * math.pi, 49)], 'style': st, 'elem': eid, 'layer': 'annotation'})
        for aid in fl.get('m_arrowIds') or []:
            a = self.f.rec(self.f.eid(aid), 'InteriorElevArrow')
            if not a: continue
            bs = a['fields'].get('m_boundedSpace') or {}
            if not bs.get('m_basis'): continue
            d = (Mv @ np.asarray(bs['m_basis'][2], float))[:2]
            if np.linalg.norm(d) < 1e-9: continue
            d /= np.linalg.norm(d)
            if af.get('m_shape') == 0:
                # square body (2020 Residential '1/2" Square'): triangle on the side the arrow looks to, base = that side, apex angle 2 x half
                n = np.array([-d[1], d[0]]); tip = c[:2] + d * (rad + rad / math.tan(half))
                loop = [tip.tolist(), (c[:2] + d * rad + n * rad).tolist(), (c[:2] + d * rad - n * rad).tolist(), tip.tolist()]
            else:
                tip = c[:2] + d * rad / math.cos(half)
                ang = math.atan2(d[1], d[0])
                arc = [(c[:2] + rad * np.array([math.cos(t), math.sin(t)])).tolist() for t in np.linspace(ang - (math.pi / 2 - half), ang + (math.pi / 2 - half), 9)]
                loop = [tip.tolist()] + arc[::-1] + [tip.tolist()]
            if af.get('m_ahFilled', 1): out.append({'t': 'fill', 'loops': [loop], 'color': [0, 0, 0], 'elem': eid, 'layer': 'annotation_fill'})
            else: out.append({'t': 'line', 'pts': loop, 'style': st, 'elem': eid, 'layer': 'annotation'})
            out += self.arrow_labels(eid, a, d, c, rad, af, sym, scale)
        return out

    def arrow_labels(self, eid, a, d, c, rad, af, sym, scale):
        """detail number (viewport) beside the arrow, sheet number (symbol label) at the body centre: 2020 Residential plan 32 DXF G-ANNO-SYMB
        (number centre = marker + arrow direction x 1.4 x body radius, 0.33 ft above at 1:48; text 3/32\" high)"""
        vid = self.f.eid(a['fields'].get('m_dbViewId'))
        ref = self.d.dec.__dict__.setdefault('_vp_of_view', None)
        if ref is None:
            ref = {}
            for sh in self.doc['views'].values():
                if sh.get('kind') == 'sheet':
                    for vp in sh.get('viewports') or []: ref[vp['view']] = (vp.get('detail_number'), sh.get('sheetNumber'))
            self.d.dec.__dict__['_vp_of_view'] = ref
        if vid not in ref: return []
        dn, sn = ref[vid]
        from .sheet import SheetComposer
        out = []
        font = self.doc['fonts'].get(self.f.eid(ob(af.get('m_lineAndTextAttr')).get('m_fontId'))) if af.get('m_lineAndTextAttr') else None
        size = ((font or {}).get('size') or 3 / 32 * IN) * scale; name = (font or {}).get('name') or 'Arial'
        if dn:
            p0 = c[:2] + d * 1.4 * rad + np.array([0.0, 0.33 / 48 * scale])
            out.append({'t': 'text', 'text': str(dn), 'origin': p0.tolist(), 'x': [1.0, 0.0], 'size': size, 'font': name, 'halign': 1, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
        if sn and sym not in (None, INVALID):
            for lab in (self.d.dec.titleblock_symbol(sym) or {}).get('labels', []):
                if any(prm.get('name') == 'Sheet Number' for prm in lab.get('params') or []):
                    org = np.asarray(lab['origin'], float)[:2] * scale + c[:2]
                    out.append({'t': 'text', 'text': str(sn), 'origin': org.tolist(), 'x': [1.0, 0.0], 'size': size, 'font': name, 'halign': 1, 'valign': 1, 'anchor': True, 'elem': eid, 'layer': 'text'})
        return out


def section_marker(drawer, eid, O, Mv, scale, res, vid, pts=None):
    """section marker in a plan: the section line (Section.m_frontCut polyline, jogs included), the type's head symbol at the first point and
    tail symbol at the last (SectionAttributes.m_sectionHeadFamilyTagId / m_sectionTailFamilyTagId), labels = detail / sheet number of the
    section view's viewport. Symbol frame: local -x outward along the line (labels sit at x < 0), local y = the section's looking direction (?)."""
    from . import gfx
    from .sheet import SheetComposer
    f = drawer.f; doc = drawer.doc
    r = f.rec(eid, 'Section')
    if not r: return []
    fl = r['fields']; given = pts is not None; pts = pts if pts is not None else (fl.get('m_frontCut') or [])
    if len(pts) < 2: return []
    tv = f.eid(fl.get('m_dbViewId')); vrec = f.rec(tv)
    vt = f.rec(f.eid(vrec['fields'].get('m_dbViewTypeId'))) if vrec else None
    at = f.rec(f.eid(vt['fields'].get('m_sectionAttrId'))) if vt else None
    af = at['fields'] if at else {}
    P = np.asarray([((np.asarray(p, float) - O) @ Mv.T)[:2] for p in pts])
    if not given and (doc['views'].get(vid) or {}).get('kind') == 'plan':
        P = _section_visible(P, fl.get('m_boundedSpace') or {}, O, Mv, (doc['views'].get(vid) or {}), scale)
        if P is None: return []
    st = res.line(None, -2000200, 'proj', eid, annotation=True)
    out = [{'t': 'line', 'pts': P.tolist(), 'style': st, 'elem': eid, 'layer': 'annotation', 'part': 'line'}]
    bs = fl.get('m_boundedSpace') or {}
    look = (Mv @ np.asarray(bs['m_basis'][2], float))[:2] if bs.get('m_basis') else np.array([0.0, 1.0])
    look = look / (np.linalg.norm(look) or 1)
    vp = next((vp for s in doc['sheets'].values() for vp in s['viewports'] if vp['view'] == tv), None)
    sheet = next((s for s in doc['sheets'].values() for x in s['viewports'] if x['view'] == tv), None)
    vals = {'Detail Number': (vp or {}).get('detail_number') or '', 'Sheet Number': (sheet or {}).get('sheetNumber') or '',
            'Reference Label': ((vt or {'fields': {}})['fields'].get('m_refLabelStr') or '') if fl.get('m_bIsViewerReference') else ''}      # reference sections ('Reference Other View') show their view type's label ('typ.')
    # jogged sections (Residential A-2, Commercial 173630: Revit DXF) carry the full head at BOTH ends; straight ones head + tail box (A-3)
    tail_key = 'm_sectionHeadFamilyTagId' if len(pts) > 2 else 'm_sectionTailFamilyTagId'
    for end, sym_key in ((0, 'm_sectionHeadFamilyTagId'), (len(P) - 1, tail_key)):
        sid = f.eid(af.get(sym_key))
        if sid in (None, INVALID): continue
        nb = P[1] if end == 0 else P[-2]
        d = P[end] - nb; d = d / (np.linalg.norm(d) or 1)                  # outward along the line
        x = -d; y = look if abs(float(look @ d)) < 0.99 else np.array([-d[1], d[0]])
        R = np.array([[x[0], y[0], 0], [x[1], y[1], 0], [0, 0, 1.0]]) * scale
        o = np.array([P[end][0], P[end][1], 0.0])
        sp = symbol_prims(drawer, sid, R, o, eid, res, -2000200)
        out += sp
        labs = [lab for lab in (drawer.dec.titleblock_symbol(sid) or {}).get('labels', [])
                if ' '.join(label_str(vals.get(prm.get('name'), '')) for prm in lab.get('params') or []).strip()]
        # Revit keeps the head's labels upright and stacked: the anchor (centre of the labels) turns with the line, the offsets do not
        L = np.asarray([lab['origin'][:2] for lab in labs], float) if labs else np.zeros((0, 2))
        c = L.mean(0) if len(L) else np.zeros(2)
        cw = gfx.transform_pts([[c[0], c[1], 0.0]], R, o)[0]
        if len(labs) >= 2:
            ys = L[:, 1]
            if ys.max() - ys.min() > 1e-6:                                   # divider between the stacked labels (Revit draws one)
                rad = abs(float(c[0])) * scale
                ymid = cw[1] + (np.median(ys) - c[1]) * scale
                out.append({'t': 'line', 'pts': [[cw[0] - rad, ymid], [cw[0] + rad, ymid]], 'style': res.line(None, -2000200, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation'})
        for lab in labs:
            txt = ' '.join(label_str(vals.get(prm.get('name'), '')) for prm in lab.get('params') or []).strip()
            if not txt: continue
            tt = doc['text_types'].get(lab['type']) or {}
            font = doc['fonts'].get(tt.get('font')) or {}
            org = [cw[0] + (lab['origin'][0] - c[0]) * scale, cw[1] + (lab['origin'][1] - c[1]) * scale]
            out.append({'t': 'text', 'text': txt, 'origin': org[:2], 'x': [1.0, 0.0], 'size': (font.get('size') or 0.0078) * scale, 'font': font.get('name') or 'Arial',
                        'halign': SheetComposer._halign(lab['flags'] or 0), 'valign': SheetComposer._valign(lab['flags'] or 0), 'anchor': True, 'elem': eid, 'layer': 'text'})
    return out


def _section_visible(P, bs, O, Mv, v, scale):
    """section line in a plan: the front cut polyline clipped to the section view's own crop width (m_boundedSpace: origin + basis[0] * [lo, hi];
    Commercial 'Building Section' in an uncropped plan: x -79.9 .. 85.5 becomes -78.4 .. 79.4, the symbols sit at the clipped ends), then to the
    plan's crop region (inset 0.2375\" of paper, Commercial Mezzanine: edge -35.9, head at -37.8)"""
    from .datums import Datums
    from .compose import crop_rect_uv
    try:
        bo = bs['m_boundOffset'][0]; B0 = np.asarray(bs['m_basis'][0], float); org = np.asarray(bs['m_orig'], float)
        ax = (Mv @ B0)[:2]; ax = ax / (np.linalg.norm(ax) or 1.0)
        c0 = float(((org - O) @ Mv.T)[:2] @ ax)
        lo, hi = c0 + min(bo[0], bo[1]) , c0 + max(bo[0], bo[1])        # (hi, lo) stored; coordinates along the section's right axis in view units
        nrm = np.array([-ax[1], ax[0]]); cs = [(lo, hi)]
    except Exception:
        return P
    tol = 0.125 / 12 * scale                       # overshoots up to 1/8" of paper are kept (Residential section A-3: 0.5 ft at 1:48 stays unclamped)
    e0 = min(float(P[0] @ ax), float(P[-1] @ ax)); e1 = max(float(P[0] @ ax), float(P[-1] @ ax))
    if 0 < lo - e0 <= tol: lo = e0
    if 0 < e1 - hi <= tol: hi = e1
    rects = []
    cr = crop_rect_uv(v)
    if cr is not None and max(P[:, 0].max() - cr[2], cr[0] - P[:, 0].min(), P[:, 1].max() - cr[3], cr[1] - P[:, 1].min()) < 3.0 * scale / 96.0:
        return P         # cropped plan whose crop hardly cuts the line (Commercial Level 1, view 32: Revit shows the full line, heads at both ends): unchanged (rule unknown)
    if cr is not None:
        ins = 0.2375 / 12 * scale
        rects.append((cr[0] + ins, cr[1] + ins, cr[2] - ins, cr[3] - ins))
    # clip against the slab lo <= p.ax <= hi (and the crop rect)
    def clip_slab(a, b):
        da = float(a @ ax); db = float(b @ ax); d = db - da
        t0, t1 = 0.0, 1.0
        if abs(d) < 1e-12:
            return (a, b) if lo - 1e-9 <= da <= hi + 1e-9 else None
        ta, tb = (lo - da) / d, (hi - da) / d
        if ta > tb: ta, tb = tb, ta
        t0, t1 = max(t0, ta), min(t1, tb)
        return (a + (b - a) * t0, a + (b - a) * t1) if t0 <= t1 else None
    vis = []
    for a, b in zip(P[:-1], P[1:]):
        sg = clip_slab(a, b)
        for rc in rects:
            if sg is not None: sg = Datums._clip(sg[0], sg[1], rc)
        if sg is not None: vis.append(sg)
    if not vis: return None
    Q = [vis[0][0]]
    for a, b in vis:
        if np.linalg.norm(a - Q[-1]) > 1e-6: Q.append(a)
        Q.append(b)
    return np.asarray(Q)


def section_head_extent(drawer, eid):
    """outward extent (paper feet) of the section type's head symbol along its local -x axis (the direction away from the line): where the line must stop for the symbol to lie inside a clip rectangle"""
    c = drawer.__dict__.setdefault('_hext', {})
    f = drawer.f; doc = drawer.doc
    r = f.rec(eid, 'Section')
    if not r: return None
    fl = r['fields']; tv = f.eid(fl.get('m_dbViewId')); vrec = f.rec(tv)
    vt = f.rec(f.eid(vrec['fields'].get('m_dbViewTypeId'))) if vrec else None
    at = f.rec(f.eid(vt['fields'].get('m_sectionAttrId'))) if vt else None
    sid = f.eid(((at or {}).get('fields') or {}).get('m_sectionHeadFamilyTagId'))
    if sid in (None, INVALID): return None
    if sid not in c:
        class _R:
            def line(self, *a, **k): return {'w': 0.1}
        sp = symbol_prims(drawer, sid, np.eye(3), np.zeros(3), eid, _R(), -2000200)
        pts = [q for p in sp for q in (p.get('pts') or [q for l in p.get('loops', []) for q in l])]
        c[sid] = float(-np.asarray(pts, float)[:, 0].min()) if pts else None
    return c[sid]


def symbol_prims(drawer, sid, R, o, eid, res, cat):
    """2D symbol graphics (annotation family type) placed with R (3x3, includes the paper->model scale) at o, through the scene walker in 2D
    mode: reference planes skipped, filled regions (face fills) as fills + styled boundaries, nested symbols followed"""
    from .scene import Walker, ViewCtx
    W = Walker(drawer.f, ViewCtx(np.array([0.0, 0.0, 1.0]), kind='drafting', scale=1))
    W.invisible_gs = {g for g, st in drawer.doc['gstyles'].items() if 'nvisible' in str((drawer.doc['categories'].get(st.get('cat')) or {}).get('name'))}
    pc = W.walk_record(sid, np.asarray(R, float), np.asarray(o, float))
    out = []
    for p in pc['curves']:
        if p.get('pts'): out.append({'t': 'line', 'pts': [q[:2] for q in p['pts']], 'style': res.line(p.get('gs'), cat, 'proj', eid, annotation=True), 'gs': p.get('gs'), 'elem': eid, 'layer': 'annotation'})
    for p in pc['fills']:
        pat = drawer.doc['fill_patterns'].get(p.get('pattern'))
        if p.get('loops') and (pat is None or pat.get('solid')) and not ((p.get('fill_flags') or 0) & 4 and False):
            out.append({'t': 'fill', 'loops': [[q[:2] for q in l] for l in p['loops']], 'color': [0, 0, 0], 'elem': eid, 'layer': 'annotation_fill'})
    return out


def callout(drawer, eid, O, Mv, scale, res, vid):
    """callout (Section record, m_sectionCreationMethod 202) in its parent view: the callout view's crop box (m_boundedSpace, basis rows 0/1,
    m_boundOffset [hi, lo]) as a rectangle with rounded corners (CalloutTag.m_cornerRadius, paper), a straight leader to the head point
    (m_viewDataMapForCallout[parent].m_headPoint) and the head symbol (CalloutTag.m_familyTagId) upright at the head point with the callout
    view's detail / sheet number (2020 Residential 'typ. wall' callouts, vs Revit's DXF)"""
    from . import gfx
    from .sheet import SheetComposer
    f = drawer.f; doc = drawer.doc
    r = f.rec(eid, 'Section')
    if not r: return []
    fl = r['fields']; bs = fl.get('m_boundedSpace') or {}
    if not bs.get('m_basis') or not bs.get('m_boundOffset'): return []
    tv = f.eid(fl.get('m_dbViewId')); vrec = f.rec(tv)
    vt = f.rec(f.eid(vrec['fields'].get('m_dbViewTypeId'))) if vrec else None
    at = f.rec(f.eid(vt['fields'].get('m_calloutAttrId'))) if vt else None
    af = at['fields'] if at else {}
    o = np.asarray(bs['m_orig'], float); B = np.asarray(bs['m_basis'], float); bo = bs['m_boundOffset']
    corners = [o + B[0] * u + B[1] * w for u, w in ((bo[0][1], bo[1][1]), (bo[0][0], bo[1][1]), (bo[0][0], bo[1][0]), (bo[0][1], bo[1][0]))]
    C2 = np.asarray([((p - O) @ Mv.T)[:2] for p in corners])
    st = res.line(None, -2000278, 'proj', eid, annotation=True)
    out = []
    from shapely.geometry import Polygon, Point
    poly = Polygon(C2)
    if poly.area <= 1e-9: return []
    rad = float(af.get('m_cornerRadius') or 0) * scale
    if rad > 0 and rad * 2 < min(np.ptp(C2[:, 0]), np.ptp(C2[:, 1])):
        poly = poly.buffer(-rad, join_style=2).buffer(rad, resolution=8)
    stb = res.line(None, -2000539, 'proj', eid, annotation=True)          # 'Callout Boundary' subcategory: pen 8, Dash 1/8" (Revit DXF: linetype 'Dash 1_8_', lineweight 1.4 mm)
    out.append({'t': 'line', 'pts': [list(q) for q in poly.exterior.coords], 'style': stb, 'elem': eid, 'layer': 'annotation'})
    vd = next((x['second'] for x in fl.get('m_viewDataMapForCallout') or [] if f.eid(x.get('first')) == vid), None)
    sid = f.eid(af.get('m_familyTagId'))
    if not vd or vd.get('m_headPoint') is None or sid in (None, INVALID): return out
    h = ((np.asarray(vd['m_headPoint'], float) - O) @ Mv.T)[:2]
    R = np.eye(3) * scale; ho = np.array([h[0], h[1], 0.0])
    sp = symbol_prims(drawer, sid, R, ho, eid, res, -2000278)
    out += sp
    # leader: straight, from the box outline towards the head, stopping at the head symbol's extent
    P = np.asarray([q for p in sp for q in (p.get('pts') or [])], float) if sp else np.zeros((0, 2))
    hr = float(np.max(np.hypot(P[:, 0] - h[0], P[:, 1] - h[1]))) if len(P) else 0.0
    from shapely.ops import nearest_points
    a = np.asarray(nearest_points(poly.exterior, Point(h))[0].coords[0])
    dv = h - a; L = np.linalg.norm(dv)
    if L > 1e-6 and hr > 0:
        # the head point is where the leader meets the head: Revit places the head circle one radius beyond it, along the leader (typ. wall callouts vs the DXF)
        sh = dv / L * hr
        for p_ in sp:
            if p_.get('pts'): p_['pts'] = [[q[0] + sh[0], q[1] + sh[1]] + list(q[2:]) for q in p_['pts']]
            if p_.get('origin') is not None: p_['origin'] = [p_['origin'][0] + sh[0], p_['origin'][1] + sh[1]] + list(p_['origin'][2:])
            if p_.get('loops'): p_['loops'] = [[[q[0] + sh[0], q[1] + sh[1]] + list(q[2:]) for q in l] for l in p_['loops']]
        h = h + sh
    if L > 1e-6 and L > 0: out.append({'t': 'line', 'pts': [a.tolist(), (h - dv / L * hr).tolist()], 'style': st, 'elem': eid, 'layer': 'annotation'})
    vp = next((x for s in doc['sheets'].values() for x in s['viewports'] if x['view'] == tv), None)
    sheet = next((s for s in doc['sheets'].values() for x in s['viewports'] if x['view'] == tv), None)
    vals = {'Detail Number': (vp or {}).get('detail_number') or '', 'Sheet Number': (sheet or {}).get('sheetNumber') or '',
            'Reference Label': (((f.rec(f.eid((f.rec(tv) or {'fields': {}})['fields'].get('m_dbViewTypeId'))) or {'fields': {}})['fields'].get('m_refLabelStr') or '') if fl.get('m_bIsViewerReference') else '')}      # reference callouts show their view type's label ('typ.')
    for lab in (drawer.dec.titleblock_symbol(sid) or {}).get('labels', []):
        txt = ' '.join(label_str(vals.get(prm.get('name'), '')) for prm in lab.get('params') or []).strip()
        if not txt: continue
        tt = doc['text_types'].get(lab['type']) or {}
        font = doc['fonts'].get(tt.get('font')) or {}
        org = [h[0] + lab['origin'][0] * scale, h[1] + lab['origin'][1] * scale]
        out.append({'t': 'text', 'text': txt, 'origin': org, 'x': [1.0, 0.0], 'size': (font.get('size') or 0.0078) * scale, 'font': font.get('name') or 'Arial',
                    'halign': SheetComposer._halign(lab['flags'] or 0), 'valign': SheetComposer._valign(lab['flags'] or 0), 'anchor': True, 'elem': eid, 'layer': 'text'})
    return out
