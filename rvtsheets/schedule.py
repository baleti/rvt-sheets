"""Schedules on sheets (ScheduleInstance, title block revision schedules) as sheet primitives.
Definition (DBViewSchedule): m_pSchema {m_pFields [heading, column width, param id, hidden], m_sortFieldArr, m_filterArr, m_categoryId,
m_bInstanceSchedule, m_showTitle, m_showHeaders, m_bFixedHeight, m_altScheduleTitle}, m_pData (section row heights), m_segmentRecords
(fixed height), title/header/body text types. Rows are computed from the elements of the category (instances or types), values from the
reader's parameter values by parameter name. Layout: ScheduleInstance origin = top-left corner (checked against the oracle bbox)."""
import os
import numpy as np
from .reader import ob, path, INVALID


ANNOTATION_SYMBOLS = -2000150                                            # Generic Annotations


class Schedules:
    def __init__(self, composer):
        self.sc = composer; self.f = composer.f; self.doc = composer.doc; self.dec = composer.dec
        self._params = None

    def params(self):
        if self._params is None:
            try: self._params = self.f.params()
            except Exception: self._params = {}
        return self._params

    def old_em(self, d):
        """True for 2020-2021 style files: text em = type size / 0.72 and row pitch 1.917 x type size (Commercial PDFs); False for 2022+ (Snowdon calibration kept)"""
        if os.environ.get('RVT_SCHED_EM', 'new') != 'new': return False
        try:
            from .units import is_2022_plus
            return not is_2022_plus(self.f)
        except Exception: return True

    def em_k(self, d):
        """text em / type size in a schedule: Revit 2022+ files draw schedule text at size / 0.72 like notes (Snowdon PDF: header 15.6 pt vs 3/32in note 11.85 pt = 1.32 ~ 1.33), 2020 files at 1.2 x (Window Schedule PNG: 'x\' - x\"' ink width)"""
        if os.environ.get('RVT_SCHED_FIT', '1') != '1': return 0.8 if d.get('grid_lines', 1) else 1.2
        if d.get('grid_lines') == 0 and os.environ.get('RVT_SCHED_GL', '1') != '1': return 1.2
        if d.get('grid_lines') == 0: return 1 / 0.72      # gridless lists: em = type size / 0.72 (Commercial cover sheet PDF, Sheet List: 1/4in type printed 25 pt = 8.82 mm)
        if os.environ.get('RVT_SCHED_EM', 'new') == 'new': return 1 / 0.72      # Commercial 2020 PDFs: Door Schedule header 4.41 mm / body 3.35 mm, How Do I table 4.41 mm = type size / 0.72 as in 2022+ files
        try:
            from .units import is_2022_plus
            if is_2022_plus(self.f): return 1 / 0.72
        except Exception: pass
        return 1.2

    def font(self, tid):
        tt = self.doc['text_types'].get(self.f.eid(tid)) or {}
        fo = self.doc['fonts'].get(tt.get('font')) or {}
        return fo.get('size') or 3 / 32 / 12, fo.get('name') or 'Arial', tt.get('bold')

    def definition(self, sid):
        r = self.f.rec(sid, 'DBViewSchedule')
        if not r: return None
        fl = r['fields']; sch = ob(fl.get('m_pSchema')) or {}
        fields = []; all_fields = []
        for i, fd in enumerate(sch.get('m_pFields') or []):
            o = ob(fd) or {}
            pid = self.f.eid(o.get('m_paramElemId'))
            x = {'heading': o.get('m_columnHeading') or '', 'width': o.get('m_columnWidth') or 0.08, 'param': pid, 'index': i,
                 'groups': list(o.get('m_headerIds') or []),
                 'pname': self.dec.param_names.get(str(pid)), 'source': o.get('m_sourceType')}
            all_fields.append(x)
            if not o.get('m_hidden'): fields.append(x)
        data = ob(fl.get('m_pData')) or {}
        secs = [ob(s) for s in data.get('m_SectionData') or []]
        def rowh(i, d):
            try: return ob(secs[i]['m_rows'][0]).get('m_dHeight') or d
            except Exception: return d
        def rowh_i(sec, i):
            try: return ob(sec['m_rows'][i]).get('m_dHeight')
            except Exception: return None
        segs = [ob(s) for s in fl.get('m_segmentRecords') or []]
        fids = [(ob(x) or {}).get('m_id') for x in sch.get('m_fieldIds') or []]
        # header section rows after the title row: merged note rows ('To learn more about ...' in the Commercial 'How Do I' schedule)
        hdr_rows = []; title_size = None
        try:
            sd0 = ob(secs[0])
            c00 = ob(ob(ob(sd0['m_tableCells'][0])['m_arrCells'][0]).get('m_oTableCellStyle')) or {}
            title_size = (c00.get('m_textSize') or 0) / 100 / 12 or None
            for ri, tc in enumerate(sd0.get('m_tableCells') or []):
                if ri == 0: continue
                cells = [ob(c) for c in ob(tc).get('m_arrCells') or []]
                txt = next((str(c.get('m_text')) for c in cells if c.get('m_text')), '')
                if not txt: continue
                c = next(c for c in cells if c.get('m_text')); st = ob(c.get('m_oTableCellStyle')) or {}
                hdr_rows.append({'text': txt, 'size': (st.get('m_textSize') or 12.0) / 100 / 12, 'font': st.get('m_fontName') or 'Arial',
                                 'halign': (ob(st.get('m_oHelper')) or {}).get('m_horAlignment') or 0, 'height': rowh_i(sd0, ri)})
        except Exception: hdr_rows = []
        return {'name': fl.get('m_viewName'), 'title': sch.get('m_altScheduleTitle') or fl.get('m_viewName'), 'fields': fields,
                'show_title': sch.get('m_showTitle', 1), 'show_headers': sch.get('m_showHeaders', 1), 'initial_spacer': sch.get('m_showInitialSpacer'),
                'grid_lines': sch.get('m_showGridLines', 1), 'outline': sch.get('m_showOutline', 1), 'fixed': sch.get('m_bFixedHeight'),
                'height': (segs[0].get('m_height') if segs else None), 'title_h': rowh(0, 1 / 24), 'body_h': rowh(1, 1 / 72),
                'category': self.f.eid(sch.get('m_categoryId')), 'instance': sch.get('m_bInstanceSchedule', 1),
                'filters': [(path(x, 'm_fieldId', 'm_id'), (ob(x) or {}).get('m_filterType'), (ob((ob(x) or {}).get('m_value')) or {})) for x in sch.get('m_filterArr') or []],
                'sort': [(path(s, 'm_fieldId', 'm_id'), (ob(s) or {}).get('m_sortOrder', 0)) for s in sch.get('m_sortFieldArr') or []],
                'field_ids': fids, 'header_rows': hdr_rows, 'title_size': title_size, 'all_fields': all_fields, 'header_set': {h.get('m_id'): h.get('m_caption') or '' for h in (ob(x) for x in sch.get('m_headerSet') or []) if h},
                'fonts': {k: self.font(fl.get(k)) for k in ('m_titleTextTypeId', 'm_headerTextTypeId', 'm_bodyTextTypeId')},
                'grid_gs': self.sc.cat_gstyle(self.f.eid(sch.get('m_bodyGridCategoryId'))), 'outline_gs': self.sc.cat_gstyle(self.f.eid(sch.get('m_outlineGridCategoryId'))), 'medium_gs': self.sc.cat_gstyle(-2000043), 'tb_inst': self.f.eid(sch.get('m_titleBlockInstId'))}

    def rev_rows(self, d, sheet_id):
        """revision schedule of a title block: one row per revision listed on the sheet (sheet m_explicitlyPresentRevisionIds, ascending sequence number): number, description, date, issued by / to"""
        if os.environ.get('RVT_REVROWS', '1') != '1' or sheet_id is None: return []
        try:
            r = self.f.rec(sheet_id)
            ids = [self.f.eid(x) for x in (r['fields'].get('m_explicitlyPresentRevisionIds') or [])]
            revs = [self.f.rec(i) for i in ids]; revs = [x for x in revs if x]
            revs.sort(key=lambda x: x['fields'].get('m_sequenceNumber') or 0)
            out = []
            for rv in revs:
                fl = rv['fields']
                vals = {'umber': str(fl.get('m_numberStr') or ''), 'escription': str(fl.get('m_description') or ''), 'ate': str(fl.get('m_date') or ''), 'ssued by': str(fl.get('m_issuedBy') or ''), 'ssued to': str(fl.get('m_issuedTo') or '')}
                row = []
                for f in d['fields']:
                    nm = str(f.get('pname') or f.get('heading') or '')
                    row.append(next((v for k, v in vals.items() if k in nm), ''))
                out.append(row)
            return out
        except Exception: return []

    def rows(self, d, sheet_id=None):
        """element rows: elements of the category (instances unless a type schedule); revision schedules: revisions shown on the sheet (?)"""
        cat = d['category']; out = []
        if cat == -2003100:                                              # Sheets: one row per sheet (number, name, ...)
            sheets = sorted(self.doc['sheets'].values(), key=lambda x: str(x.get('sheetNumber')))
            from .sheet import SHEET_FIELDS
            def cell(sh, fd):
                n = fd.get('pname') or fd['heading']
                if n in ('Sheet Number', 'Number'): return str(sh.get('sheetNumber') or '')
                if n in ('Sheet Name', 'Name'): return str(sh.get('name') or '')
                if fd.get('param') in SHEET_FIELDS:                   # built-in sheet parameters live in the sheet record (Drawn By, Checked By, Approved By, ...)
                    r = self.f.rec(sh.get('id'))
                    v = ((r or {'fields': {}})['fields'].get(SHEET_FIELDS[fd['param']]))
                    if v not in (None, ''): return str(v)
                return str((sh.get('params') or {}).get(n, ''))
            return [[cell(sh, fd) for fd in d['fields']] for sh in sheets]
        for eid, e in self.sc_vis_info().items():
            if e['cat'] != cat or (e['owner'] not in (INVALID,) and cat != ANNOTATION_SYMBOLS): continue      # generic annotations (help icons) are view-owned but still listed
            if bool(e['type']) == bool(d['instance']): continue
            p = (self.params().get(eid) or {}).get('params') or {}
            sk = []
            for fid, order in d.get('sort') or []:
                af = (d.get('all_fields') or []); fi = d.get('field_ids') or []
                if fid in fi: fid = fi.index(fid)                       # sort fields name a field id (m_fieldIds order = field order), not an index
                if isinstance(fid, int) and 0 <= fid < len(af):
                    v = self.value(eid, af[fid], p)
                    k = (0, float(v), '') if isinstance(v, (int, float)) and not isinstance(v, bool) else (1, 0.0, str(v or ''))
                    sk.append((k, order))
            if d.get('filters') and os.environ.get('RVT_SCHED_FILTER', '1') == '1' and not self._passes(eid, d, p): continue
            out.append((eid, sk, [self.cell_text(eid, fd, p) for fd in d['fields']]))
        # schedule sort fields (m_sortFieldArr: field index incl. hidden fields, m_sortOrder 1 = descending), then element order
        out.sort(key=lambda r: r[0])
        for i in reversed(range(max((len(r[1]) for r in out), default=0))):
            out.sort(key=lambda r: r[1][i][0] if i < len(r[1]) else (2, 0.0, ''), reverse=bool(out and i < len(out[0][1]) and out[0][1][i][1]))
        return [r[2] for r in out]

    def _passes(self, eid, d, p):
        """schedule filters (m_filterArr: field id, internal type = API ScheduleFilterType + 2: 3 not equal, 9 does not contain, ...; value m_str / m_dbl); all must hold.
        Commercial 'How Do I' (type 3, ''): the row without a topic is not listed (Revit's table is one row shorter)"""
        fi = d.get('field_ids') or []; af = d.get('all_fields') or []
        for fid, typ, val in d['filters']:
            if fid in fi: k = fi.index(fid)
            else: k = fid if isinstance(fid, int) else -1
            if not (0 <= k < len(af)): continue
            raw = self.value(eid, af[k], p); txt = str(self.cell_text(eid, af[k], p) or '')
            sv = str(((val.get('m_str') or {}) if isinstance(val.get('m_str'), dict) else {'m_str': val.get('m_str')}).get('m_str') or '')
            a, b = txt.lower(), sv.lower()
            num = isinstance(raw, (int, float)) and not isinstance(raw, bool); dv = val.get('m_dbl') or 0.0
            ok = {2: a == b, 3: a != b, 8: b in a, 9: b not in a, 10: a.startswith(b), 11: not a.startswith(b), 12: a.endswith(b), 13: not a.endswith(b)}.get(typ)
            if typ in (4, 5, 6, 7) and num: ok = {4: raw > dv, 5: raw >= dv, 6: raw < dv, 7: raw <= dv}[typ]
            if ok is None: continue
            if not ok: return False
        return True

    def cell_text(self, eid, fd, named):
        v = self.value(eid, fd, named)
        if v is None and fd['heading'].rstrip().endswith('?') and fd['param'] in self._raw(eid): v = False       # a Yes/No parameter stored as 0
        if v is None and fd['heading'].rstrip().endswith('?') and self._raw_has(eid, fd['param']): v = False
        return self.fmt(v, fd['pname'])

    def _raw_has(self, eid, pid):
        r = self.f.rec(eid)
        return any(self.f.eid(e.get('m_paramId')) == pid for e in (ob((r or {'fields': {}})['fields'].get('m_pInstParams')) or {}).get('m_params') or [])

    def value(self, eid, fd, named):
        """cell value by parameter id: the element's stored values, then its type's (derived symbols -> master type, family type
        parameters by caption through rvt_params.symbol_params), then the reader's named parameters"""
        pid = fd['param']
        raw = self._raw(eid)
        if pid in raw and raw[pid] not in (None, ''): return raw[pid]
        tp = self._type_params(eid)
        if pid in tp and tp[pid] not in (None, ''): return tp[pid]
        v = named.get(fd['pname'])
        if v is None and fd['pname'] in tp: v = tp[fd['pname']]
        if v is None and pid == -1001362:                            # Head Height (not stored): sill elevation + type height
            r = self.f.rec(eid); h = tp.get(-1001300)
            el = (r or {'fields': {}})['fields'].get('m_elevation')
            if isinstance(h, (int, float)) and isinstance(el, (int, float)): v = float(el) + float(h)
        return v

    def _raw(self, eid):
        out = {}
        r = self.f.rec(eid)
        for e in (ob((r or {'fields': {}})['fields'].get('m_pInstParams')) or {}).get('m_params') or []:        # annotation symbols keep their instance values here
            pid = self.f.eid(e.get('m_paramId'))
            if isinstance(pid, int) and pid not in out:
                out[pid] = e['m_str'] if e.get('m_str') else (e.get('m_int') if e.get('m_int') else (e.get('m_value') or None))
        for k in ('m_pParamValueSetAString', 'm_pParamValueSetDouble', 'm_pParamValueSetInt', 'm_pParamValueSetElementId'):
            for e in (ob((r or {'fields': {}})['fields'].get(k)) or {}).get('m_paramSet') or []:
                pid = e.get('m_paramId')
                if isinstance(pid, int): out[pid - 2 ** 32 if pid >= 2 ** 31 else pid] = e.get('m_value')
        return out

    def _type_params(self, eid):
        r = self.f.rec(eid)
        ii = ob((r or {'fields': {}})['fields'].get('m_pInstanceInfo')) or {}
        sym = self.f.eid(ii.get('m_symbolId')) if ii else None
        if sym in (None, INVALID): return {}
        c = self.__dict__.setdefault('_tp', {})
        if sym not in c:
            try:
                import rvt_params
                c[sym] = dict(rvt_params.symbol_params(self.f.fn, sym))
            except Exception: c[sym] = {}
            # built-in type values kept in the (master) symbol's m_pParams under unsigned built-in ids (window Width -1001301 = 2.5,
            # Height -1001300 = 4.0 on 2020 Residential type 159300); not in symbol_params yet (NEEDS-FROM-READER.md item 3)
            chain = [sym]
            while len(chain) < 4:
                rr = self.f.rec(chain[-1]); m = self.f.eid((rr or {'fields': {}})['fields'].get('m_masterId'))
                if m in (None, INVALID) or m in chain: break
                chain.append(m)
            for t in chain:
                rr = self.f.rec(t)
                for e in (ob((rr or {'fields': {}})['fields'].get('m_pParams')) or {}).get('m_params') or []:
                    pid = e.get('m_paramId')
                    if not isinstance(pid, int) or pid < 2 ** 31: continue
                    pid -= 2 ** 32
                    v = e['m_str'] if e.get('m_str') else (e.get('m_value') if e.get('m_value') else e.get('m_int'))
                    c[sym].setdefault(pid, v)
        return c[sym]

    def sc_vis_info(self):
        if not hasattr(self, '_info'):
            from .visibility import ElementInfo
            self._info = ElementInfo(self.dec).info
        return self._info

    LENGTHS = ('Length', 'Offset', 'Width', 'Height', 'Elevation', 'Thickness', 'Depth', 'Perimeter', 'Diameter', 'Radius', 'Size')

    def fmt(self, v, pname=''):
        """schedule cell text: element ids -> element / type / family names, lengths in project units"""
        from . import units
        if v is None: return ''
        pname = pname or ''
        if isinstance(v, bool): return 'Yes' if v else 'No'
        if isinstance(v, int) and not isinstance(v, bool) and (abs(v) > 1000 or v == -1) and pname not in ('Count',):
            if v == -1: return ''
            return self.name_of(v, pname)
        if isinstance(v, float):
            if any(w in pname for w in self.LENGTHS): return units.fmt_length(v, {'m_bUseDefault': 1}, units.length_format(self.f))
            if 'Area' in pname: return ('%.2f m²' % (v * 0.09290304)) if not units.is_imperial(self.f) else '%d SF' % round(v)
            if 'Volume' in pname: return ('%.2f m³' % (v * 0.028316846592)) if not units.is_imperial(self.f) else '%.2f CF' % v
            return '%g' % v
        return str(v)

    def name_of(self, eid, pname=''):
        r = self.f.rec(eid)
        if not r: return str(eid)
        fl = r['fields']
        if pname == 'Family' and 'm_familyId' in fl:
            fam = self.f.rec(self.f.eid(fl['m_familyId']))
            if fam and fam['fields'].get('m_name'): return fam['fields']['m_name']
        if pname == 'Family and Type' and 'm_familyId' in fl:
            fam = self.f.rec(self.f.eid(fl['m_familyId']))
            return '%s: %s' % ((fam or {'fields': {}})['fields'].get('m_name', ''), (ob(fl.get('m_symbolInfo')) or {}).get('m_name', ''))
        for k in ('m_symbolInfo', 'm_name', 'm_viewName', 'm_text'):
            v = fl.get(k)
            if isinstance(v, dict): v = (ob(v) or {}).get('m_name')
            if isinstance(v, str) and v: return v
        return str(eid)

    def prims(self, sched_id, origin, sheet_id=None):
        d = self.definition(sched_id)
        if not d or not d['fields']: return []
        x0, y0 = origin[0], origin[1]
        W = sum(f['width'] for f in d['fields'])
        rows = self.rev_rows(d, sheet_id) if d['tb_inst'] not in (None, INVALID) else self.rows(d, sheet_id)       # title block revision schedules: the revisions present on the sheet
        out = []; y = y0
        def line(a, b, heavy=False):
            if d.get('grid_lines') == 0: return
            gs_ = d['medium_gs'] if heavy == 'mid' and d.get('outline') and d.get('medium_gs') is not None and os.environ.get('RVT_SCHED_OUTLINE', '1') == '1' else d['outline_gs'] if heavy and d.get('outline') and d.get('outline_gs') is not None and os.environ.get('RVT_SCHED_OUTLINE', '1') == '1' else d['grid_gs']
            out.append({'t': 'line', 'pts': [[a[0], a[1], 0], [b[0], b[1], 0]], 'gs': gs_, 'cond': [], 'elem': sched_id, 'w_min': 0.457 if heavy is True and os.environ.get('RVT_SCHED_LW', '1') == '1' else 0.0})      # Revit PDFs (pt widths): schedule outline 1.3 pt = 0.457 mm (Commercial Door Schedule verticals, Snowdon Sheet Index), inner grid 0.24 pt = 0.085 mm black
        def text(s, x, yy, w, h, font, halign=1):
            size, name, bold = font
            size *= 0.72 * self.em_k(d)
            out.append({'t': 'text', 'text': s, 'origin': [x + (w / 2 if halign == 1 else 0.004), yy - h / 2, 0], 'x': [1, 0, 0], 'size': size, 'font': name, 'bold': bold,
                        'halign': halign, 'valign': 1, 'anchor': True, 'cond': [], 'gs': None, 'elem': sched_id})
        if d['show_title']:
            h = d['title_h']
            if d.get('title_size') and d.get('header_rows'): text(d['title'], x0, y, W, h, (d['title_size'] / (0.72 * self.em_k(d)), 'Arial', 0))   # explicit cell text size (a schedule with a styled header section) is drawn at size / 0.72
            else: text(d['title'], x0, y, W, h, d['fonts']['m_titleTextTypeId'])
            if d.get('grid_lines', 1) and os.environ.get('RVT_SCHED_FIT', '1') == '1':          # the title row is boxed by the grid (Revit Window Schedule export: lines at the title's top, left and right edges)
                line((x0, y), (x0 + W, y), True); line((x0, y), (x0, y - h), True); line((x0 + W, y), (x0 + W, y - h), True); line((x0, y - h), (x0 + W, y - h), 'mid')
            y -= h
        from .viewdraw import wrap_text
        for hr in d.get('header_rows') or []:                                # merged note rows under the title (clipped to the row height with '...' like Revit)
            em = hr['size'] / 0.72; pitch = em * 1.22; hh = hr['height'] or pitch
            lines = wrap_text(hr['text'], W - 0.008, em, hr['font']).split('\n')
            maxl = max(1, int(hh / pitch + 0.05))
            if len(lines) > maxl:
                lines = lines[:maxl]; lines[-1] = lines[-1].rstrip() + '...'
            out.append({'t': 'text', 'text': '\n'.join(lines), 'origin': [x0 + 0.004, y - max(0.0, (hh - len(lines) * pitch) / 2) - 0.0005, 0], 'x': [1, 0, 0], 'size': hr['size'],
                        'font': hr['font'], 'bold': False, 'halign': 0, 'valign': 0, 'anchor': True, 'cond': [], 'gs': None, 'elem': sched_id})
            if d.get('grid_lines', 1) and os.environ.get('RVT_SCHED_FIT', '1') == '1':
                line((x0, y - hh), (x0 + W, y - hh)); line((x0, y), (x0, y - hh)); line((x0 + W, y), (x0 + W, y - hh))
            y -= hh
        hb = d['body_h'] or d['fonts']['m_bodyTextTypeId'][0] * 2.2
        if d.get('grid_lines') == 0: hb = max(hb, d['fonts']['m_bodyTextTypeId'][0] * (1.917 if os.environ.get('RVT_SCHED_GL', '1') == '1' else 1.2 * 0.72 * 1.8))   # gridless lists: rows follow the larger text
        elif os.environ.get('RVT_SCHED_FIT', '1') == '1': hb = max(hb, d['fonts']['m_bodyTextTypeId'][0] * (1.917 if (self.old_em(d) or os.environ.get('RVT_SCHED_P', 'new') == 'new') else 1.597 * self.em_k(d)))      # Door Schedule PDF: body pitch 4.565 mm = 1.917 x 3/32in, header rows 6.09 mm = 1.917 x 1/8in, Sheet List 12.17 mm = 1.917 x 1/4in   # Revit's rows follow the text (2020 Window Schedule export: pitch 0.0199 ft vs stored 0.0139)
        hh = hb
        if d.get('grid_lines') != 0 and os.environ.get('RVT_SCHED_FIT', '1') == '1' and os.environ.get('RVT_SCHED_HDR', '1') == '1':
            bs_, hs_ = d['fonts']['m_bodyTextTypeId'][0], d['fonts']['m_headerTextTypeId'][0]
            if bs_ and hs_ and hs_ > bs_: hh = hb * hs_ / bs_      # heading rows follow the (larger) heading text like the body rows follow theirs (Commercial Door Schedule PDF: 2 x 6.09 mm heading rows vs 4.57 mm body rows)
        if d.get('grid_lines') == 0 and not d['show_headers'] and d['show_title'] and os.environ.get('RVT_SCHED_GL', '1') == '1': y -= hb      # hidden heading row keeps its height (Commercial Sheet List PDF: first row 2 pitches below the title)
        top_grid = y
        inner = set()                                    # x of column boundaries inside a header group (no line through the group row)
        if d['show_headers'] and any(f.get('groups') for f in d['fields']):
            # grouped headings (m_headerSet, field m_headerIds): group captions over their columns, other headings span both rows
            h = hh; x = x0; hf = d['fonts']['m_headerTextTypeId']; i = 0; fs = d['fields']
            line((x0, y), (x0 + W, y), 'mid')
            while i < len(fs):
                g = fs[i]['groups'][0] if fs[i].get('groups') else None
                if g is None:
                    hd = fs[i]['heading']; fit = os.environ.get('RVT_SCHED_FIT', '1') == '1'
                    est = len(hd) * 0.55 * hf[0] * self.em_k(d)                        # Arial average advance ~0.5 em
                    if fit and ' ' in hd and est > fs[i]['width'] - 0.004:            # a heading wider than its column wraps: two lines, one per heading row (Revit: 'Head' / 'Height')
                        a_, b_ = hd.split(' ', 1) if hd.count(' ') == 1 else (hd[:hd.rfind(' ')], hd[hd.rfind(' ') + 1:])
                        text(a_, x, y, fs[i]['width'], h, hf); text(b_, x, y - h, fs[i]['width'], h, hf)
                    else: text(hd, x, (y - h) if fit else (y - h / 2), fs[i]['width'], h, hf)                       # a single line sits in the lower heading row (Revit 'Type Mark')
                    x += fs[i]['width']; i += 1; continue
                j = i; gw = 0.0
                while j < len(fs) and (fs[j]['groups'][:1] == [g]): gw += fs[j]['width']; j += 1
                text(d['header_set'].get(g, ''), x, y, gw, h, hf)
                line((x, y - h), (x + gw, y - h))
                xx = x
                for f in fs[i:j]:
                    text(f['heading'], xx, y - h, f['width'], h, hf); xx += f['width']
                    if xx < x + gw - 1e-9: inner.add(round(xx, 9))
                x += gw; i = j
            y -= 2 * h; line((x0, y), (x0 + W, y), 'mid'); header_top = y + 2 * h
        elif d['show_headers']:
            h = hh; x = x0; hf = d['fonts']['m_headerTextTypeId']; wrap = os.environ.get('RVT_SCHED_WRAP', '1') == '1'
            lp = hf[0] * self.em_k(d) * 1.26 if wrap else 0.0          # headings wider than their column wrap at the space (Snowdon Sheet Index PDF: 'Sheet' / 'Number'); the row grows by a text line and the lines sit at its bottom
            def lines_of(f):
                hd = f['heading']
                if wrap and ' ' in hd and len(hd) * 0.56 * hf[0] * self.em_k(d) > f['width'] - 0.004: return hd.split(' ', 1) if hd.count(' ') == 1 else [hd[:hd.rfind(' ')], hd[hd.rfind(' ') + 1:]]
                return [hd]
            nl = max(len(lines_of(f)) for f in d['fields']); extra = (nl - 1) * lp; h = hh + extra
            for f in d['fields']:
                ls = lines_of(f)
                for i, t_ in enumerate(ls): text(t_, x, y - extra + (len(ls) - 1 - i) * lp, f['width'], hh, hf)
                x += f['width']
            line((x0, y), (x0 + W, y), 'mid'); y -= h; line((x0, y), (x0 + W, y), 'mid')
        gap = None
        if d['show_headers'] and d.get('grid_lines', 1) and d.get('initial_spacer') and os.environ.get('RVT_SCHED_FIT', '1') == '1':
            gap = y; y -= hb; line((x0, y), (x0 + W, y))                  # 'blank row before data': one body-height row without grid between the headings and the first row (Revit Window Schedule export)
        n = len(rows)
        if d['fixed'] and d['height']:
            n = max(n, int((d['height'] - (y0 - y)) / hb + 1e-6))
        bsize, bname, bbold = d['fonts']['m_bodyTextTypeId']; bem = bsize * self.em_k(d)
        for i in range(n):
            rh = hb
            if i < len(rows):
                x = x0
                cells = [wrap_text(v, f['width'] - 0.008, bem, bname, bool(bbold)) for f, v in zip(d['fields'], rows[i])]
                nl = max((c.count('\n') + 1 for c in cells), default=1)
                if nl > 1: rh = hb + (nl - 1) * bem * 1.22                      # a long value wraps inside its column and the row grows (Revit 'How Do I': two-line rows)
                for f, v, c in zip(d['fields'], rows[i], cells):
                    if nl > 1 and c:
                        out.append({'t': 'text', 'text': c, 'origin': [x + 0.004, y - (hb - bem) / 2 - 0.0005, 0], 'x': [1, 0, 0], 'size': bsize * 0.72 * self.em_k(d), 'font': bname,
                                    'bold': bbold, 'halign': 0, 'valign': 0, 'anchor': True, 'cond': [], 'gs': None, 'elem': sched_id})
                    else: text(c, x, y, f['width'], hb, d['fonts']['m_bodyTextTypeId'], halign=0)
                    x += f['width']
            y -= rh; line((x0, y), (x0 + W, y))
        x = x0
        for f in d['fields'] + [None]:
            # inside a header group the column line starts below the group caption
            hv = f is None or x == x0
            if gap is None: line((x, top_grid - (hh if round(x, 9) in inner else 0)), (x, y), hv)
            else: line((x, top_grid - (hh if round(x, 9) in inner else 0)), (x, gap), hv); line((x, gap), (x, gap - hb), hv); line((x, gap - hb), (x, y), hv)
            if f: x += f['width']
        return out
