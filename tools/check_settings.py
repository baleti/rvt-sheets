"""check_settings.py FILE.rvt [ORACLE.views] -> per-field agreement table of decoded view/sheet settings vs the Revit oracle.
Prints one row per field: n compared, n equal, % and the first mismatches."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets import oracle

DETAIL = {1: 'Coarse', 2: 'Medium', 3: 'Fine'}
DISCIPLINE = {1: 'Architectural', 2: 'Structural', 4: 'Mechanical', 8: 'Electrical', 16: 'Plumbing', 4095: 'Coordination'}
RANGE_IDX = {'CutPlane': 0, 'TopClipPlane': 1, 'BottomClipPlane': 2, 'ViewDepthPlane': 3, 'UnderlayBottom': 4}
OV_MAP = {'ProjectionLineWeight': 'proj_weight', 'CutLineWeight': 'cut_weight', 'ProjectionLineColor': 'proj_color', 'CutLineColor': 'cut_color',
          'ProjectionLinePatternId': 'proj_pattern', 'CutLinePatternId': 'cut_pattern', 'SurfaceForegroundPatternId': 'surf_fg_pattern', 'SurfaceBackgroundPatternId': 'surf_bg_pattern',
          'CutForegroundPatternId': 'cut_fg_pattern', 'CutBackgroundPatternId': 'cut_bg_pattern', 'SurfaceForegroundPatternColor': 'surf_fg_color', 'SurfaceBackgroundPatternColor': 'surf_bg_color',
          'CutForegroundPatternColor': 'cut_fg_color', 'CutBackgroundPatternColor': 'cut_bg_color', 'Halftone': 'halftone', 'Transparency': 'transparency', 'DetailLevel': 'detail_level',
          'IsSurfaceForegroundPatternVisible': 'surf_fg_visible', 'IsSurfaceBackgroundPatternVisible': 'surf_bg_visible', 'IsCutForegroundPatternVisible': 'cut_fg_visible',
          'IsCutBackgroundPatternVisible': 'cut_bg_visible',
          # older API names (2020)
          'ProjectionFillPatternId': 'surf_fg_pattern', 'ProjectionFillColor': 'surf_fg_color', 'CutFillPatternId': 'cut_fg_pattern', 'CutFillColor': 'cut_fg_color',
          'IsProjectionFillPatternVisible': 'surf_fg_visible', 'IsCutFillPatternVisible': 'cut_fg_visible'}


def ov_norm_oracle(ov):
    out = {}
    for k, v in ov.items():
        m = OV_MAP.get(k)
        if not m: out['?' + k] = v; continue
        if m.endswith('color'): out[m] = [int(a) for a in v.split(',')] if v not in ('none', '') else None
        elif m in ('halftone',) or m.endswith('visible'): out[m] = v == 'True'
        elif m == 'detail_level': out[m] = {'Coarse': 1, 'Medium': 2, 'Fine': 3, 'Undefined': 0}.get(v, v)
        else:
            try: out[m] = int(v)
            except ValueError: out[m] = v
    return {k: v for k, v in out.items() if v is not None}


class Table:
    def __init__(self): self.rows = collections.OrderedDict()
    def add(self, field, ok, why=''):
        r = self.rows.setdefault(field, [0, 0, []])
        r[0] += 1; r[1] += bool(ok)
        if not ok and len(r[2]) < 4: r[2].append(why)
    def show(self):
        for k, (n, ok, ex) in self.rows.items():
            print('%-34s %6d %6d %6.1f%%  %s' % (k, n, ok, 100.0 * ok / max(n, 1), ' | '.join(str(e)[:110] for e in ex)))


def main():
    fn = sys.argv[1]; ofn = sys.argv[2] if len(sys.argv) > 2 else oracle.find(fn)
    o = oracle.load(ofn); dec = Decoder(fn); d = dec.doc()
    T = Table(); views = d['views']
    for vid, ov in o['views'].items():
        v = views.get(vid)
        T.add('view.found', v is not None, vid)
        if v is None: continue
        T.add('view.name', v['name'] == ov['name'], (vid, v['name'], ov['name']))
        T.add('view.template', v['template'] == ov['template'], vid)
        if ov.get('Scale') and ov['Scale'] != '0': T.add('view.scale', str(v.get('scale')) == ov['Scale'], (vid, v.get('scale'), ov['Scale']))
        if ov.get('DetailLevel') and ov['DetailLevel'] != 'Undefined': T.add('view.detail_level', DETAIL.get(v.get('detail_level')) == ov['DetailLevel'], (vid, v.get('detail_level'), ov['DetailLevel']))
        if ov.get('Discipline'): T.add('view.discipline', DISCIPLINE.get(v.get('discipline')) == ov['Discipline'], (vid, v.get('discipline'), ov['Discipline']))
        if ov.get('phase') not in (None, '-1'): T.add('view.phase', str(v.get('phase')) == ov['phase'], (vid, v.get('phase'), ov['phase']))
        if ov.get('phaseFilter') not in (None, '-1'): T.add('view.phase_filter', str(v.get('phase_filter')) == ov['phaseFilter'], (vid, v.get('phase_filter'), ov['phaseFilter']))
        if 'ViewTemplateId' in ov: T.add('view.view_template', str(v.get('view_template')) == ov['ViewTemplateId'], (vid, v.get('view_template'), ov['ViewTemplateId']))
        if 'CropBoxActive' in ov and v.get('crop'):
            act = v['crop']['crop_active']
            T.add('view.crop_active (m_boundActive x/y)', act == (ov['CropBoxActive'] == 'True'), (vid, v['crop'].get('active'), ov['CropBoxActive']))
        if vid in o['crop'] and v.get('crop') and v['crop'].get('bounds'):
            oc = o['crop'][vid]; mn = oracle.vec(oc['min']); mx = oracle.vec(oc['max'])
            b = v['crop']['bounds']
            okb = all(abs(b[i][0] - mx[i]) < 1e-6 and abs(b[i][1] - mn[i]) < 1e-6 for i in range(2))
            T.add('view.crop_xy (bounds=[max,min])', okb, (vid, b[:2], mn[:2], mx[:2]))
        if vid in o['range'] and v.get('range'):
            for nm, (lv, off) in o['range'][vid].items():
                i = RANGE_IDX[nm]
                T.add('range.offset', abs(v['range']['offsets'][i] - off) < 1e-9, (vid, nm, v['range']['offsets'][i], off))
                T.add('range.level', v['range']['levels'][i] == lv, (vid, nm, v['range']['levels'][i], lv))
        # V/G: hidden categories
        if vid in o['catvis']:
            exc = set()
            for df in v.get('draw_filters') or []: exc |= set(df.get('m_categoryIds') or [])
            for cid, cv in o['catvis'][vid].items():
                if cv['hidden']: T.add('vg.category_hidden (in excluded set)', cid in exc, (vid, cid))
                if cv['ov']:
                    mine = v['category_overrides'].get(cid) or v['category_overrides'].get(str(cid)) or {}
                    exp = ov_norm_oracle(cv['ov'])
                    T.add('vg.category_overrides', all(mine.get(k) == x for k, x in exp.items()), (vid, cid, mine, exp))
        if vid in o['vfilter']:
            mine = v.get('filters') or []
            T.add('filters.count', len(mine) == len(o['vfilter'][vid]), (vid, len(mine), len(o['vfilter'][vid])))
            byid = {x['filter']: x for x in mine}
            # the oracle lists View.GetFilters() = ascending element id, NOT the UI priority order: compare by id (priority order needs GetOrderedFilters, see NEEDS-FROM-ORACLE)
            T.add('filters.same_set', set(byid) == {x['filter'] for x in o['vfilter'][vid]}, (vid,))
            for i, of in enumerate(o['vfilter'][vid]):
                m = byid.get(of['filter'])
                if m is None: continue
                T.add('filters.visible', m['visible'] == of['visible'], (vid, of['filter']))
                exp = ov_norm_oracle(of['ov']); got = m['overrides'] or {}
                T.add('filters.overrides', all(got.get(k) == x for k, x in exp.items()) and all(k in exp for k in got), (vid, of['filter'], got, exp))
        if vid in o['eovr']:
            for eid, ev in o['eovr'][vid].items():
                got = v['element_overrides'].get(eid) or v['element_overrides'].get(str(eid)) or {}
                exp = ov_norm_oracle(ev)
                T.add('element_overrides', all(got.get(k) == x for k, x in exp.items()), (vid, eid, got, exp))
        # sheet params
    for fid, of in o['filters'].items():
        m = d['filters'].get(fid)
        T.add('filter.found', m is not None, fid)
        if m:
            T.add('filter.name', m['name'] == of['name'], fid)
            T.add('filter.categories', sorted(m['categories']) == sorted(of['cats']), (fid, sorted(m['categories'])[:5], sorted(of['cats'])[:5]))
    # sheets / viewports
    vpmine = {vp['id']: (sid, vp) for sid, s in d['sheets'].items() for vp in s['viewports']}
    for vpid, ovp in o['viewports'].items():
        m = vpmine.get(vpid)
        T.add('viewport.found', m is not None, vpid)
        if not m: continue
        sid, vp = m
        T.add('viewport.sheet', str(sid) == ovp['sheet'], vpid); T.add('viewport.view', str(vp['view']) == ovp['view'], vpid)
        ovw = o['views'].get(vp['view'], {})
        if ovw.get('outline'):
            (u0, v0), (u1, v1) = [oracle.vec(x) for x in ovw['outline'].split(':')]
            c = oracle.vec(ovp['center'])
            pred = (vp['offset'][0] + (u0 + u1) / 2, vp['offset'][1] + (v0 + v1) / 2)
            if u0 == u1 == v0 == v1 == 0: pred = (vp['offset'][0] + 0.1, vp['offset'][1] + 0.075)        # empty view: Revit shows a 0.2 x 0.15 ft placeholder box from the offset
            T.add('viewport.center = offset + outline centre', abs(pred[0] - c[0]) < 1e-6 and abs(pred[1] - c[1]) < 1e-6, (vpid, pred, c[:2]))
            T.add('viewport.scale', abs(1 / vp['scale'] - float(ovw.get('Scale', 0))) < 1e-6, vpid)
    for tid, ot in o['titleblocks'].items():
        s = d['sheets'].get(int(ot['sheet']))
        T.add('titleblock.found', bool(s) and any(t['id'] == tid and str(t['symbol']) == ot['symbol'] for t in s['titleblocks']), tid)
    for sid, os_ in o['sheets'].items():
        s = d['sheets'].get(sid)
        T.add('sheet.found', s is not None, sid)
        if s: T.add('sheet.number', s.get('sheetNumber') == os_['number'], (sid, s.get('sheetNumber'), os_['number']))
    # object styles
    for gid, og in o['gstyles'].items():
        m = d['gstyles'].get(gid)
        T.add('gstyle.found', m is not None, gid)
    for cid, oc in o['cats'].items():
        m = d['categories'].get(cid)
        if not m: T.add('category.found', False, cid); continue
        T.add('category.found', True)
        for kind, k in (('proj', 'projW'), ('cut', 'cutW')):
            if oc.get(k) and oc[k] != '':
                T.add('category.%s_weight' % kind, str((m.get(kind) or {}).get('pen')) == oc[k], (cid, oc['name'], (m.get(kind) or {}).get('pen'), oc[k]))
        if oc.get('color') and oc['color'] != 'none' and m.get('proj'):
            T.add('category.color', (m['proj'].get('color') or [0, 0, 0]) == [int(a) for a in oc['color'].split(',')], (cid, oc['name'], m['proj'].get('color'), oc['color']))
    for lid, (nm, segs) in o['lpat'].items():
        m = d['line_patterns'].get(lid)
        T.add('line_pattern.found', m is not None, lid)
        if m:
            exp = [(s.split(':')[0], float(s.split(':')[1])) for s in segs.split(';') if s]
            got = [({0: 'Dash', 1: 'Space', 2: 'Dot'}.get(t, t), l) for t, l in m['segments']]
            T.add('line_pattern.segments', len(exp) == len(got) and all(a[0] == b[0] and abs(a[1] - b[1]) < 1e-9 for a, b in zip(exp, got)), (lid, got, exp))
    T.show()


if __name__ == '__main__': main()
