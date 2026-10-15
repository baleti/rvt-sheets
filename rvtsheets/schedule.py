"""Schedules on sheets (ScheduleInstance, title block revision schedules) as sheet primitives.
Definition (DBViewSchedule): m_pSchema {m_pFields [heading, column width, param id, hidden], m_sortFieldArr, m_filterArr, m_categoryId,
m_bInstanceSchedule, m_showTitle, m_showHeaders, m_bFixedHeight, m_altScheduleTitle}, m_pData (section row heights), m_segmentRecords
(fixed height), title/header/body text types. Rows are computed from the elements of the category (instances or types), values from the
reader's parameter values by parameter name. Layout: ScheduleInstance origin = top-left corner (checked against the oracle bbox)."""
import numpy as np
from .reader import ob, path, INVALID


class Schedules:
    def __init__(self, composer):
        self.sc = composer; self.f = composer.f; self.doc = composer.doc; self.dec = composer.dec
        self._params = None

    def params(self):
        if self._params is None:
            try: self._params = self.f.params()
            except Exception: self._params = {}
        return self._params

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
        segs = [ob(s) for s in fl.get('m_segmentRecords') or []]
        return {'name': fl.get('m_viewName'), 'title': sch.get('m_altScheduleTitle') or fl.get('m_viewName'), 'fields': fields,
                'show_title': sch.get('m_showTitle', 1), 'show_headers': sch.get('m_showHeaders', 1),
                'grid_lines': sch.get('m_showGridLines', 1), 'outline': sch.get('m_showOutline', 1), 'fixed': sch.get('m_bFixedHeight'),
                'height': (segs[0].get('m_height') if segs else None), 'title_h': rowh(0, 1 / 24), 'body_h': rowh(1, 1 / 72),
                'category': self.f.eid(sch.get('m_categoryId')), 'instance': sch.get('m_bInstanceSchedule', 1),
                'sort': [(path(s, 'm_fieldId', 'm_id'), (ob(s) or {}).get('m_sortOrder', 0)) for s in sch.get('m_sortFieldArr') or []],
                'all_fields': all_fields, 'header_set': {h.get('m_id'): h.get('m_caption') or '' for h in (ob(x) for x in sch.get('m_headerSet') or []) if h},
                'fonts': {k: self.font(fl.get(k)) for k in ('m_titleTextTypeId', 'm_headerTextTypeId', 'm_bodyTextTypeId')},
                'grid_gs': self.sc.cat_gstyle(self.f.eid(sch.get('m_bodyGridCategoryId'))), 'tb_inst': self.f.eid(sch.get('m_titleBlockInstId'))}

    def rows(self, d, sheet_id=None):
        """element rows: elements of the category (instances unless a type schedule); revision schedules: revisions shown on the sheet (?)"""
        cat = d['category']; out = []
        if cat == -2003100:                                              # Sheets: one row per sheet (number, name, ...)
            sheets = sorted(self.doc['sheets'].values(), key=lambda x: str(x.get('sheetNumber')))
            def cell(sh, fd):
                n = fd.get('pname') or fd['heading']
                if n in ('Sheet Number', 'Number'): return str(sh.get('sheetNumber') or '')
                if n in ('Sheet Name', 'Name'): return str(sh.get('name') or '')
                return str((sh.get('params') or {}).get(n, ''))
            return [[cell(sh, fd) for fd in d['fields']] for sh in sheets]
        for eid, e in self.sc_vis_info().items():
            if e['cat'] != cat or e['owner'] not in (INVALID,): continue
            if bool(e['type']) == bool(d['instance']): continue
            p = (self.params().get(eid) or {}).get('params') or {}
            sk = []
            for fid, order in d.get('sort') or []:
                af = (d.get('all_fields') or [])
                if isinstance(fid, int) and 0 <= fid < len(af):
                    v = self.value(eid, af[fid], p)
                    k = (0, float(v), '') if isinstance(v, (int, float)) and not isinstance(v, bool) else (1, 0.0, str(v or ''))
                    sk.append((k, order))
            out.append((eid, sk, [self.fmt(self.value(eid, fd, p), fd['pname']) for fd in d['fields']]))
        # schedule sort fields (m_sortFieldArr: field index incl. hidden fields, m_sortOrder 1 = descending), then element order
        out.sort(key=lambda r: r[0])
        for i in reversed(range(max((len(r[1]) for r in out), default=0))):
            out.sort(key=lambda r: r[1][i][0] if i < len(r[1]) else (2, 0.0, ''), reverse=bool(out and i < len(out[0][1]) and out[0][1][i][1]))
        return [r[2] for r in out]

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
        rows = [] if d['tb_inst'] not in (None, INVALID) else self.rows(d, sheet_id)       # title block revision schedules: issued revisions (none in the samples)
        out = []; y = y0
        def line(a, b):
            if d.get('grid_lines') == 0: return
            out.append({'t': 'line', 'pts': [[a[0], a[1], 0], [b[0], b[1], 0]], 'gs': d['grid_gs'], 'cond': [], 'elem': sched_id})
        def text(s, x, yy, w, h, font, halign=1):
            size, name, bold = font
            size *= 0.72 * (0.8 if d.get('grid_lines', 1) else 1.2)      # cell-fitted sizes with grid (Window Schedule export); gridless sheet lists use the type size
            out.append({'t': 'text', 'text': s, 'origin': [x + (w / 2 if halign == 1 else 0.004), yy - h / 2, 0], 'x': [1, 0, 0], 'size': size, 'font': name, 'bold': bold,
                        'halign': halign, 'valign': 1, 'anchor': True, 'cond': [], 'gs': None, 'elem': sched_id})
        if d['show_title']:
            h = d['title_h']; text(d['title'], x0, y, W, h, d['fonts']['m_titleTextTypeId']); y -= h
        hb = d['body_h'] or d['fonts']['m_bodyTextTypeId'][0] * 2.2
        if d.get('grid_lines') == 0: hb = max(hb, d['fonts']['m_bodyTextTypeId'][0] * 1.2 * 0.72 * 1.8)   # gridless lists: rows follow the larger text
        top_grid = y
        inner = set()                                    # x of column boundaries inside a header group (no line through the group row)
        if d['show_headers'] and any(f.get('groups') for f in d['fields']):
            # grouped headings (m_headerSet, field m_headerIds): group captions over their columns, other headings span both rows
            h = hb; x = x0; hf = d['fonts']['m_headerTextTypeId']; i = 0; fs = d['fields']
            line((x0, y), (x0 + W, y))
            while i < len(fs):
                g = fs[i]['groups'][0] if fs[i].get('groups') else None
                if g is None:
                    text(fs[i]['heading'], x, y - h / 2, fs[i]['width'], h, hf); x += fs[i]['width']; i += 1; continue
                j = i; gw = 0.0
                while j < len(fs) and (fs[j]['groups'][:1] == [g]): gw += fs[j]['width']; j += 1
                text(d['header_set'].get(g, ''), x, y, gw, h, hf)
                line((x, y - h), (x + gw, y - h))
                xx = x
                for f in fs[i:j]:
                    text(f['heading'], xx, y - h, f['width'], h, hf); xx += f['width']
                    if xx < x + gw - 1e-9: inner.add(round(xx, 9))
                x += gw; i = j
            y -= 2 * h; line((x0, y), (x0 + W, y)); header_top = y + 2 * h
        elif d['show_headers']:
            h = hb; x = x0
            for f in d['fields']: text(f['heading'], x, y, f['width'], h, d['fonts']['m_headerTextTypeId']); x += f['width']
            line((x0, y), (x0 + W, y)); y -= h; line((x0, y), (x0 + W, y))
        n = len(rows)
        if d['fixed'] and d['height']:
            n = max(n, int((d['height'] - (y0 - y)) / hb + 1e-6))
        for i in range(n):
            if i < len(rows):
                x = x0
                for f, v in zip(d['fields'], rows[i]): text(v, x, y, f['width'], hb, d['fonts']['m_bodyTextTypeId'], halign=0); x += f['width']
            y -= hb; line((x0, y), (x0 + W, y))
        x = x0
        for f in d['fields'] + [None]:
            # inside a header group the column line starts below the group caption
            line((x, top_grid - (hb if round(x, 9) in inner else 0)), (x, y))
            if f: x += f['width']
        return out
