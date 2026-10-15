"""Stage 2: compose a sheet: title block (symbol saved graphics + static texts + labels with the sheet's parameter values) and viewports.
Output: a 'drawing' dict {size:[w,h] ft, prims:[...]} in sheet feet coordinates, styles resolved (stroke mm, rgb, dash mm)."""
import datetime
import numpy as np
from . import gfx
from .decode import Decoder, color, FT_MM, SOLID_LINE
from .reader import ob, path, INVALID

# label parameter id -> sheet record field (built-in sheet parameters stored as DBView fields)
SHEET_FIELDS = {-1007400: 'm_viewName', -1007401: 'm_sheetNumber', -1007404: 'm_drawnBy', -1007405: 'm_checkedBy', -1006322: 'm_issueDate',
                -1007407: 'm_designedBy', -1007408: 'm_approvedBy'}
P_SCALE, P_DATESTAMP = -1007402, -1007403


class Styler:
    """graphics style id -> stroke (mm), rgb, dash (mm); annotation (paper) pens"""
    def __init__(self, doc):
        self.doc = doc

    def gstyle(self, gs):
        return self.doc['gstyles'].get(gs) or {}

    def line(self, gs, halftone=False):
        st = self.gstyle(gs)
        pen = st.get('pen') or 1
        pens = self.doc['pens']['annotation'] if self.doc.get('pens') else None
        w = pens[pen - 1] if pens and 1 <= pen <= len(pens) else 0.18
        rgb = st.get('color') or [0, 0, 0]
        dash = None
        lp = st.get('pattern')
        if lp not in (None, INVALID, SOLID_LINE):
            pat = self.doc['line_patterns'].get(lp)
            if pat: dash = [max(s[1] * FT_MM, 0.0) if s[0] != 2 else 0.01 for s in pat['segments']]
        return {'w': w, 'rgb': rgb, 'dash': dash, 'pen': pen}


class SheetComposer:
    def __init__(self, dec: Decoder, doc=None):
        self.dec = dec; self.f = dec.f
        self.doc = doc or dec.doc()
        self.sty = Styler(self.doc)
        self._pinfo = None

    # ---------------------------------------------------------------- parameter values for labels
    def project_info(self):
        if self._pinfo is None:
            self._pinfo = {}
            for r in self.f.recs('ProjectInfo'):
                self._pinfo.update(self.dec._paramset(r['fields']))
        return self._pinfo

    def label_value(self, sheet_id, pid, sheet):
        r = self.f.rec(sheet_id)
        fl = r['fields'] if r else {}
        if pid in SHEET_FIELDS and fl.get(SHEET_FIELDS[pid]) is not None: return str(fl[SHEET_FIELDS[pid]])
        ps = self.dec._paramset(fl)
        if pid in ps: return str(ps[pid])
        pi = self.project_info()
        if pid in pi: return str(pi[pid])
        if pid == P_SCALE: return self.sheet_scale_text(sheet)
        if pid == P_DATESTAMP:
            n = datetime.datetime.now(); return '%d/%d/%d %d:%02d:%02d %s' % (n.month, n.day, n.year, (n.hour % 12) or 12, n.minute, n.second, 'AM' if n.hour < 12 else 'PM')
        return None

    def sheet_scale_text(self, sheet):
        sc = sorted({round(1 / v['scale']) for v in sheet['viewports'] if v.get('scale')})
        if not sc: return ''
        return self.scale_text(sc[0]) if len(sc) == 1 else 'As indicated'

    # ---------------------------------------------------------------- title block
    def titleblock(self, tb, sheet):
        out = []
        R = path(tb['transform'], 'm_3x3') if tb.get('transform') else None; o = path(tb['transform'], 'm_or') if tb.get('transform') else None
        g = self.f.graphics(tb['symbol'])
        if g and g.get('class') == 'GElement':
            col = gfx.Collector(self.f)
            for p in col.collect(g):
                out += self._place(p, R, o, tb['id'])
            if col.unknown: out.append({'t': 'note', 'text': 'unknown graphics nodes %s' % col.unknown})
        sym = self.doc['titleblock_symbols'].get(tb['symbol']) or self.doc['titleblock_symbols'].get(str(tb['symbol']))
        for lab in (sym or {}).get('labels', []):
            parts = []
            for prm in lab.get('params') or []:
                v = self.label_value(sheet['id'], prm['param'], sheet)
                if v is None: v = ''
                parts.append((prm.get('prefix') or '') + v + (prm.get('suffix') or ''))
            out += self._place(self._note_prim(lab, '\n'.join(parts) if len(parts) > 1 else (parts[0] if parts else '')), R, o, tb['id'])
        return out

    def _note_prim(self, n, text):
        tt = self.doc['text_types'].get(n['type']) or self.doc['text_types'].get(str(n['type'])) or {}
        font = self.doc['fonts'].get(tt.get('font')) or self.doc['fonts'].get(str(tt.get('font'))) or {}
        fl = n.get('flags') or 0
        return {'t': 'text', 'text': text, 'origin': n['origin'], 'x': n['base'], 'y': n['up'], 'size': font.get('size') or 3 / FT_MM, 'font': font.get('name') or 'Arial',
                'bold': tt.get('bold'), 'italic': tt.get('italic'), 'halign': self._halign(fl), 'valign': self._valign(fl), 'anchor': True, 'flags': fl, 'box': [n.get('width') or 0, n.get('height') or 0],
                'gs': None, 'cond': [], 'label': True}

    @staticmethod
    def _halign(flags):
        """note m_flags alignment bits (hypothesis from the A1 title block, to be checked against the oracle PDF): 0x40 left / 0x80 centre / 0x100 right"""
        if flags & 0x100: return 2
        if flags & 0x80: return 1
        return 0

    @staticmethod
    def _valign(flags):
        """0x200 top / 0x400 middle / 0x800 bottom (hypothesis)"""
        if flags & 0x800: return 2
        if flags & 0x400: return 1
        return 0

    def _place(self, p, R, o, eid):
        q = dict(p, elem=eid)
        if q['t'] == 'image':
            im = self.image(q['symbol'])
            if not im: return []
            M_ = np.asarray(q.get('R') or np.eye(3), float); oo = np.asarray(q.get('o') or [0, 0, 0], float)
            if R is not None: oo = gfx.transform_pts([oo.tolist()], R, o)[0]
            sx, sy = q.get('scale') or [1, 1]
            # image placement matrix (GImage m_Trf, composed with the symbol instance rotation): angle of its local x axis in the sheet
            Mr = np.asarray(R, float) @ M_ if R is not None else M_
            ang = float(np.arctan2(Mr[1, 0], Mr[0, 0]))
            q.update(uri=im[0], center=list(oo)[:2], w=im[1] * sx, h=im[2] * sy, angle=ang)
            return [q]
        if R is None: return [q]
        T = lambda pts: gfx.transform_pts(pts, R, o)
        if q.get('pts'): q['pts'] = T(q['pts'])
        if q.get('loops'): q['loops'] = [T(l) for l in q['loops'] if l]
        if q['t'] == 'text' and q.get('origin') is not None:
            q['origin'] = T([q['origin']])[0]
            pass
            M = np.asarray(R, float)
            if q.get('x') is not None: q['x'] = (M @ np.asarray(q['x'], float)).tolist()
            if q.get('y') is not None: q['y'] = (M @ np.asarray(q['y'], float)).tolist()
        return [q]

    # ---------------------------------------------------------------- viewport titles
    IMPERIAL = {1: '12" = 1\'-0"', 2: '6" = 1\'-0"', 4: '3" = 1\'-0"', 8: '1 1/2" = 1\'-0"', 12: '1" = 1\'-0"', 16: '3/4" = 1\'-0"', 24: '1/2" = 1\'-0"',
                32: '3/8" = 1\'-0"', 48: '1/4" = 1\'-0"', 64: '3/16" = 1\'-0"', 96: '1/8" = 1\'-0"', 128: '3/32" = 1\'-0"', 192: '1/16" = 1\'-0"',
                384: '1/32" = 1\'-0"', 120: '1" = 10\'-0"', 240: '1" = 20\'-0"', 360: '1" = 30\'-0"', 480: '1" = 40\'-0"', 600: '1" = 50\'-0"', 720: '1" = 60\'-0"'}

    def imperial(self):
        """(?) project length units: imperial when every view scale is a typical architectural imperial scale"""
        if getattr(self, '_imp', None) is None:
            sc = {v.get('scale') for v in self.doc['views'].values() if v.get('scale') and not v.get('template')}
            self._imp = bool(sc) and all(x in self.IMPERIAL for x in sc) and any(x in (48, 96, 24, 192) for x in sc)
        return self._imp

    def scale_text(self, scale):
        if self.imperial() and scale in self.IMPERIAL: return self.IMPERIAL[scale]
        return '1 : %d' % scale

    def symbol_prims(self, sid, R, o, values, eid, stretch_line=None):
        """symbol saved graphics + its labels with values {param name: text}"""
        out = []
        g = self.f.graphics(sid)
        if g and g.get('class') == 'GElement':
            col = gfx.Collector(self.f)
            for p in col.collect(g):
                if stretch_line and p['t'] == 'line' and len(p['pts']) == 2 and abs(p['pts'][0][1]) < 1e-6 and abs(p['pts'][1][1]) < 1e-6:
                    p = dict(p, pts=[[min(p['pts'][0][0], p['pts'][1][0]), 0, 0], [stretch_line, 0, 0]])
                out += self._place(p, R, o, eid)
        sym = self.dec.titleblock_symbol(sid)
        for lab in (sym or {}).get('labels', []):
            parts = [(prm.get('prefix') or '') + str(values.get(prm.get('name'), prm.get('sample') or '')) + (prm.get('suffix') or '') for prm in lab.get('params') or []]
            out += self._place(self._note_prim(lab, ' '.join(parts)), R, o, eid)
        return out

    def viewport_title(self, vp, v):
        t = self.doc['viewport_types'].get(vp['type']) or {}
        if not t.get('show_label') or t.get('title_family') in (None, INVALID): return []
        name = v.get('description') or v['name']
        vals = {'View Name': name, 'Title on Sheet': name, 'Detail Number': vp.get('detail_number') or '', 'View Scale': self.scale_text(v.get('scale') or 100),
                'Scale': self.scale_text(v.get('scale') or 100), 'Sheet Number': '', 'Sheet Name': ''}
        o = vp.get('label_origin') or vp['offset']
        out = self.symbol_prims(t['title_family'], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [o[0], o[1], 0], vals, vp['id'])
        if t.get('show_extension_line') and vp.get('label_length'):
            # the extension line is drawn by Revit, not by the title family: from the label origin over m_labelLength, in the viewport type's
            # sub-category style (?)
            out.append({'t': 'line', 'pts': [[o[0], o[1], 0], [o[0] + vp['label_length'], o[1], 0]], 'gs': self.cat_gstyle(t.get('cat')), 'cond': [], 'elem': vp['id']})
        return out

    def image(self, sid):
        """ImageSymbol -> (data uri, width ft, height ft); the PNG blob is found among the embedded images by its pixel size (?)"""
        if not hasattr(self, '_imgs'): self._imgs = {}
        if sid in self._imgs: return self._imgs[sid]
        res = None
        r = self.f.rec(sid, 'ImageSymbol')
        if r:
            fl = r['fields']; dpi = fl.get('m_dpi') or 72; w = fl.get('m_widthInFeet') or 0; h = fl.get('m_heightInFeet') or 0
            try:
                import rvt_materials as M, base64
                if not hasattr(self, '_emb'): self._emb = M.embedded_images(self.f.fn)
                W = round(w * 12 * dpi); H = round(h * 12 * dpi)
                for e in self._emb:
                    if abs(e['width'] - W) <= 1 and abs(e['height'] - H) <= 1:
                        res = ('data:image/png;base64,' + base64.b64encode(M.embedded_image_bytes(self.f.fn, e)).decode(), w, h); break
            except Exception: pass
        self._imgs[sid] = res
        return res

    def cat_gstyle(self, cid):
        c = self.doc['categories'].get(cid) or self.doc['categories'].get(str(cid)) or {}
        return (c.get('proj') or {}).get('gstyle')

    # ---------------------------------------------------------------- viewports (content comes from the view builders, stage 3+)
    def viewports(self, sheet, view_drawer=None):
        out = []
        for vp in sheet['viewports']:
            v = self.doc['views'].get(vp['view']) or self.doc['views'].get(str(vp['view']))
            if not v or v.get('kind') in ('schedule',) or (not vp.get('scale') and not (v.get('kind') == '3d' and (v.get('crop') or {}).get('proj_method') == 2)): continue
            item = {'t': 'viewport', 'vp': vp, 'view': {'id': v['id'], 'name': v['name'], 'kind': v['kind'], 'scale': v.get('scale')}, 'title': self.viewport_title(vp, v)}
            if view_drawer: item['content'] = view_drawer(v, vp)
            out.append(item)
        return out

    def compose(self, sheet_id, view_drawer=None):
        sheet = self.doc['sheets'].get(sheet_id) or self.doc['sheets'].get(str(sheet_id))
        prims = []
        size = None
        for tb in sheet['titleblocks']:
            prims += self.titleblock(tb, sheet)
            sym = self.doc['titleblock_symbols'].get(tb['symbol']) or self.doc['titleblock_symbols'].get(str(tb['symbol']))
            if sym and sym.get('outline'):
                (x0, y0, _), (x1, y1, _) = sym['outline']
                R = path(tb['transform'], 'm_3x3') if tb.get('transform') else None; o = path(tb['transform'], 'm_or') if tb.get('transform') else None
                c = gfx.transform_pts([[x0, y0, 0], [x1, y1, 0]], R, o) if R is not None else [[x0, y0], [x1, y1]]
                size = [min(c[0][0], c[1][0]), min(c[0][1], c[1][1]), max(c[0][0], c[1][0]), max(c[0][1], c[1][1])]
        if size is None: size = [0, 0, 841 / FT_MM, 594 / FT_MM]
        from .schedule import Schedules
        S = Schedules(self)
        for si in sheet.get('schedules') or []:
            try: prims += S.prims(si['schedule'], si['origin'] or [0, 0, 0], sheet['id'])
            except Exception as ex: prims.append({'t': 'note', 'text': 'schedule %s failed: %r' % (si['schedule'], ex)})
        return {'sheet': {'id': sheet['id'], 'number': sheet.get('sheetNumber'), 'name': sheet.get('name')}, 'extent': size, 'prims': prims,
                'viewports': self.viewports(sheet, view_drawer)}
