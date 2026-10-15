"""Stage 5: annotations generated from their records (Revit stores no graphics for them).
Linear dimensions (LinearDimString): references' points (m_refPnts) projected on the dimension line (m_pDimLine origin + direction),
witness lines (gap / extension), tick marks (LeaderStyle of the dimension type), segment texts at m_ArrSegInfo[i].m_origin.
Sizes are paper sizes (feet of paper) x view scale. Defaults where the type does not store a value are Revit's out-of-the-box
type values (?): witness gap 1/16", extension 3/32", tick 3/64" diagonal, text offset 1/32"."""
import math
import numpy as np
from .reader import ob, path, INVALID
from . import units

IN = 1 / 12.0


class Annotations:
    def __init__(self, drawer):
        self.d = drawer; self.f = drawer.f; self.doc = drawer.doc
        self.proj_len = units.length_format(self.f)

    def dimension(self, eid, O, Mv, scale, res):
        r = self.f.rec(eid, 'LinearDimString')
        if not r: return []
        fl = r['fields']
        dl = ob(fl.get('m_pDimLine')) or {}
        if not dl.get('m_origin'): return []
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
        out.append({'t': 'line', 'pts': [(o + d * t0).tolist(), (o + d * t1).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation'})
        for p, t in zip(refs, ts):
            q = o + d * t                       # foot on the dimension line
            v = q - p; L = np.linalg.norm(v)
            if L > gap:
                u = v / L
                out.append({'t': 'line', 'pts': [(p + u * gap).tolist(), (q + u * ext).tolist()], 'style': line, 'elem': eid, 'layer': 'annotation'})
            a = (d + n) / math.sqrt(2) * tick / 2
            out.append({'t': 'line', 'pts': [(q - a).tolist(), (q + a).tolist()], 'style': dict(tickst, w=max(tickst['w'], line['w'] * 2)), 'elem': eid, 'layer': 'annotation'})
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
            org = sg.get('m_origin')
            pos = P(org) if org and any(org) else o + d * (ts[i] + ts[i + 1]) / 2
            out.append({'t': 'text', 'text': txt, 'origin': (pos + np.array([-d_txt[1], d_txt[0]]) * size * 0.3).tolist(), 'x': d_txt.tolist(), 'size': size,
                        'font': font.get('name') or 'Arial', 'halign': 1, 'valign': 2, 'anchor': True, 'elem': eid, 'layer': 'text'})
        if not segs:
            txt = units.fmt_length(t1 - t0, ob(tf.get('m_oLinFormatOptions')) or {}, self.proj_len)
            pos = o + d * (t0 + t1) / 2
            out.append({'t': 'text', 'text': txt, 'origin': (pos + np.array([-d_txt[1], d_txt[0]]) * size * 0.3).tolist(), 'x': d_txt.tolist(), 'size': size,
                        'font': font.get('name') or 'Arial', 'halign': 1, 'valign': 2, 'anchor': True, 'elem': eid, 'layer': 'text'})
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
                parts.append((prm.get('prefix') or '') + str(v) + (prm.get('suffix') or ''))
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
        r = self.f.rec(eid, ('IndependentTag', 'RoomTag', 'SpaceTag', 'AreaTag'))
        if not r: return []
        fl = r['fields']
        sid = self.f.eid(fl.get('m_symbolId'))
        if r['class'] == 'IndependentTag':
            pos = fl.get('m_absHeadPos'); tagged = self.f.eid(path(fl, 'm_taggedElementId', 'm_linkInstOrHostId'))
        else:
            pos = fl.get('m_point'); tagged = self.f.eid(path(fl, 'm_taggedRoomElemId', 'm_linkInstOrHostId'))
            off = fl.get('m_tagOffset')
            if off and pos: pos = (np.asarray(pos, float) + np.asarray(off, float)).tolist()
        if pos is None: return []
        vals = dict(self.params_of(tagged)); raw = self.raw_params(tagged)
        # type parameters of the tagged element (Type Mark, Type Name...)
        tr = self.f.rec(tagged)
        if tr:
            ii = ob(tr['fields'].get('m_pInstanceInfo')) or {}
            sym = self.f.eid(ii.get('m_symbolId')) if ii else None
            if sym not in (None, INVALID):
                for k, v in self.params_of(sym).items(): vals.setdefault(k, v)
                for k, v in self.symbol_params(sym).items(): raw.setdefault(k, v)
        o = ((np.asarray(pos, float) - O) @ Mv.T)
        R = np.eye(3) * scale; R = Mv @ R                                   # symbol x/y (paper) -> view axes (plan: identity)
        R = np.eye(3) * scale
        out = []
        g = self.f.graphics(sid)
        if g and g.get('class') == 'GElement':
            col = gfx.Collector(self.f)
            for p in col.collect(g):
                if p['t'] == 'line':
                    pts = gfx.transform_pts(p['pts'], R, o)
                    out.append({'t': 'line', 'pts': [q[:2] for q in pts], 'style': res.line(p.get('gs'), None, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation'})
                elif p['t'] == 'fill' and p.get('loops'):
                    out.append({'t': 'fill', 'loops': [[q[:2] for q in gfx.transform_pts(l, R, o)] for l in p['loops']], 'color': p.get('color'), 'elem': eid, 'layer': 'symbolic_fill'})
        sym = self.d.dec.titleblock_symbol(sid)
        for lab in (sym or {}).get('labels', []):
            parts = []
            for prm in lab.get('params') or []:
                nm = prm.get('name') or ''
                v = raw.get(prm.get('param')) if isinstance(prm.get('param'), int) and prm.get('param') < 0 else None
                if v is None: v = vals.get(nm)
                if v is None: v = ''                                   # Revit shows an empty label when the value is missing (sample text only in the family editor)
                if isinstance(v, float):
                    if any(w in nm for w in ('Length', 'Width', 'Height', 'Elevation', 'Offset', 'Thickness', 'Depth', 'Perimeter')): v = units.fmt_length(v, {'m_bUseDefault': 1}, units.length_format(self.f))
                    elif 'Area' in nm: v = ('%d SF' % round(v)) if units.is_imperial(self.f) else ('%.2f m²' % (v * 0.09290304))
                    else: v = '%g' % v
                parts.append((prm.get('prefix') or '') + str(v) + (prm.get('suffix') or ''))
            tt = self.doc['text_types'].get(lab['type']) or {}
            font = self.doc['fonts'].get(tt.get('font')) or {}
            org = gfx.transform_pts([lab['origin']], R, o)[0]
            out.append({'t': 'text', 'text': ' '.join(parts), 'origin': org[:2], 'x': [1.0, 0.0], 'size': (font.get('size') or 0.0078) * scale,
                        'font': font.get('name') or 'Arial', 'bold': tt.get('bold'), 'halign': SheetComposer._halign(lab['flags'] or 0), 'valign': SheetComposer._valign(lab['flags'] or 0),
                        'anchor': True, 'elem': eid, 'layer': 'text'})
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
                if p['t'] == 'line' and p.get('gs') not in (None, -1): out.append({'t': 'line', 'pts': [q[:2] for q in gfx.transform_pts(p['pts'], R, c)], 'style': res.line(p.get('gs'), -2000535, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation'})
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
            d /= np.linalg.norm(d); tip = c[:2] + d * rad / math.cos(half)
            ang = math.atan2(d[1], d[0])
            arc = [(c[:2] + rad * np.array([math.cos(t), math.sin(t)])).tolist() for t in np.linspace(ang - (math.pi / 2 - half), ang + (math.pi / 2 - half), 9)]
            loop = [tip.tolist()] + arc[::-1] + [tip.tolist()]
            out.append({'t': 'fill', 'loops': [loop], 'color': [0, 0, 0], 'elem': eid, 'layer': 'annotation_fill'})
        return out


def section_marker(drawer, eid, O, Mv, scale, res, vid):
    """section marker in a plan: the section line (Section.m_frontCut polyline, jogs included), the type's head symbol at the first point and
    tail symbol at the last (SectionAttributes.m_sectionHeadFamilyTagId / m_sectionTailFamilyTagId), labels = detail / sheet number of the
    section view's viewport. Symbol frame: local -x outward along the line (labels sit at x < 0), local y = the section's looking direction (?)."""
    from . import gfx
    from .sheet import SheetComposer
    f = drawer.f; doc = drawer.doc
    r = f.rec(eid, 'Section')
    if not r: return []
    fl = r['fields']; pts = fl.get('m_frontCut') or []
    if len(pts) < 2: return []
    tv = f.eid(fl.get('m_dbViewId')); vrec = f.rec(tv)
    vt = f.rec(f.eid(vrec['fields'].get('m_dbViewTypeId'))) if vrec else None
    at = f.rec(f.eid(vt['fields'].get('m_sectionAttrId'))) if vt else None
    af = at['fields'] if at else {}
    P = np.asarray([((np.asarray(p, float) - O) @ Mv.T)[:2] for p in pts])
    st = res.line(None, -2000200, 'proj', eid, annotation=True)
    out = [{'t': 'line', 'pts': P.tolist(), 'style': st, 'elem': eid, 'layer': 'annotation'}]
    bs = fl.get('m_boundedSpace') or {}
    look = (Mv @ np.asarray(bs['m_basis'][2], float))[:2] if bs.get('m_basis') else np.array([0.0, 1.0])
    look = look / (np.linalg.norm(look) or 1)
    vp = next((vp for s in doc['sheets'].values() for vp in s['viewports'] if vp['view'] == tv), None)
    sheet = next((s for s in doc['sheets'].values() for x in s['viewports'] if x['view'] == tv), None)
    vals = {'Detail Number': (vp or {}).get('detail_number') or '', 'Sheet Number': (sheet or {}).get('sheetNumber') or '', 'Reference Label': ''}
    for end, sym_key in ((0, 'm_sectionHeadFamilyTagId'), (len(P) - 1, 'm_sectionTailFamilyTagId')):
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
                if ' '.join(str(vals.get(prm.get('name'), '')) for prm in lab.get('params') or []).strip()]
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
            txt = ' '.join(str(vals.get(prm.get('name'), '')) for prm in lab.get('params') or []).strip()
            if not txt: continue
            tt = doc['text_types'].get(lab['type']) or {}
            font = doc['fonts'].get(tt.get('font')) or {}
            org = [cw[0] + (lab['origin'][0] - c[0]) * scale, cw[1] + (lab['origin'][1] - c[1]) * scale]
            out.append({'t': 'text', 'text': txt, 'origin': org[:2], 'x': [1.0, 0.0], 'size': (font.get('size') or 0.0078) * scale, 'font': font.get('name') or 'Arial',
                        'halign': SheetComposer._halign(lab['flags'] or 0), 'valign': SheetComposer._valign(lab['flags'] or 0), 'anchor': True, 'elem': eid, 'layer': 'text'})
    return out


def symbol_prims(drawer, sid, R, o, eid, res, cat):
    """2D symbol graphics (annotation family type) placed with R (3x3, includes the paper->model scale) at o, through the scene walker in 2D
    mode: reference planes skipped, filled regions (face fills) as fills + styled boundaries, nested symbols followed"""
    from .scene import Walker, ViewCtx
    W = Walker(drawer.f, ViewCtx(np.array([0.0, 0.0, 1.0]), kind='drafting', scale=1))
    W.invisible_gs = {g for g, st in drawer.doc['gstyles'].items() if 'nvisible' in str((drawer.doc['categories'].get(st.get('cat')) or {}).get('name'))}
    pc = W.walk_record(sid, np.asarray(R, float), np.asarray(o, float))
    out = []
    for p in pc['curves']:
        if p.get('pts'): out.append({'t': 'line', 'pts': [q[:2] for q in p['pts']], 'style': res.line(p.get('gs'), cat, 'proj', eid, annotation=True), 'elem': eid, 'layer': 'annotation'})
    for p in pc['fills']:
        pat = drawer.doc['fill_patterns'].get(p.get('pattern'))
        if p.get('loops') and (pat is None or pat.get('solid')) and not ((p.get('fill_flags') or 0) & 4 and False):
            out.append({'t': 'fill', 'loops': [[q[:2] for q in l] for l in p['loops']], 'color': [0, 0, 0], 'elem': eid, 'layer': 'annotation_fill'})
    return out
