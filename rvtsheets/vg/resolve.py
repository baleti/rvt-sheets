"""Per-view graphics resolution report: for every element the view shows, the final override stack (which layer set which member) and the
resolved line styles. Data source for the viewer's hidden-line renderer and the control panel (CONTROL-API.md, 'graphics resolution').

Order (Revit): element override > view filters (earlier in the view's list win) > phase-status override (phase filter 'Overridden') > category
override (sub-category falls back to its parent category) > object style. Each layer contributes only the members it sets."""
from ..reader import INVALID
from ..style import Resolver, pen_mm
from ..visibility import Visibility, PHASE_IDX
from ..filters import FilterEval
from . import template as T


def _layers(res, view, eid, cid, fovs, fids, pov):
    """-> (merged members, {member: source}) following Resolver.overrides' order"""
    c = res._cat(cid); par = c.get('parent', INVALID)
    merged, src = {}, {}
    def put(d, name):
        for k, v in (d or {}).items(): merged[k] = v; src[k] = name
    if par != INVALID: put(res.cat_ov.get(par), 'category:%s' % par)
    put(res.cat_ov.get(cid), 'category:%s' % cid)
    put(pov, 'phase')
    for fid, fo in reversed(list(zip(fids, fovs))): put(fo, 'filter:%s' % fid)
    put(res.el_ov.get(eid), 'element')
    return merged, src


def resolve_view(dec, doc, vid, vis=None, explain=False):
    vis = vis or Visibility(dec, doc)
    v0 = doc['views'].get(vid) or doc['views'][str(vid)]
    v = vis.effective(v0)
    scale = v.get('scale') or 100
    res = Resolver(doc, v, scale); fe = FilterEval(dec, doc)
    tpl = T.template_of(doc['views'], v0)
    shown, why = vis.elements(vid, explain=True)
    out = {}
    for eid, st in shown.items():
        e = vis.info.info[eid]; cid = e['cat']
        par = (doc['categories'].get(cid) or {}).get('parent', INVALID)
        fids, fovs = [], []
        for vf in v.get('filters') or []:
            if vf.get('enabled') is False: continue
            f = doc['filters'].get(vf['filter'])
            if f and fe.matches(f, eid, cid, par): fids.append(vf['filter']); fovs.append(vf.get('overrides') or {})
        pov = None
        pf = vis.pfilters.get(v.get('phase_filter'))
        if st in PHASE_IDX and pf and pf['presentation'][PHASE_IDX[st]] == 2: pov = doc.get('phase_overrides', {}).get(PHASE_IDX[st])
        ov, src = _layers(res, v, eid, cid, fovs, fids, pov)
        row = {'cls': e['cls'], 'cat': cid, 'phase': st, 'filters': fids, 'overrides': ov, 'source': src}
        row['proj'] = res.line(None, cid, 'proj', eid, ov=ov)
        row['cut'] = res.line(None, cid, 'cut', eid, ov=ov)
        row['halftone'] = bool(ov.get('halftone'))
        row['transparency'] = ov.get('transparency', 0)
        if ov.get('detail_level'): row['detail_level'] = ov['detail_level']
        out[eid] = row
    rep = {'view': vid, 'name': v0.get('name'), 'kind': v0.get('kind'), 'scale': scale,
           'template': ({'id': tpl['id'], 'name': tpl['name'], 'controlled': T.controlled_groups(tpl)} if tpl else None),
           'detail_level': v.get('detail_level'), 'phase_filter': v.get('phase_filter'), 'discipline': v.get('discipline'),
           'filters': [{'id': vf['filter'], 'name': (doc['filters'].get(vf['filter']) or {}).get('name'), 'visible': vf.get('visible'), 'enabled': vf.get('enabled'),
                        'overrides': vf.get('overrides')} for vf in v.get('filters') or []],
           'hidden_categories': sorted(vis.hidden_categories(v)[0]), 'elements': out}
    try:
        from . import links as L
        lt = L.link_types(dec.f)
        if lt:
            vl = L.view_links(dec.f, dec.f.rec(vid)['fields']); inst = L.link_instances(dec.f)
            rep['links'] = [dict(vl.get(i['symbol'], {}), instance=iid, symbol=i['symbol'], name=lt.get(i['symbol'], {}).get('name'), origin=i['origin']) for iid, i in inst.items()]
    except Exception as ex: rep['links_error'] = repr(ex)[:200]
    if explain:
        import collections
        rep['excluded'] = dict(collections.Counter(why.values()))
        rep['excluded_ids'] = {k: w for k, w in why.items() if w in ('filter_hidden', 'hidden_element', 'category_hidden', 'phase_filter_new', 'phase_filter_existing', 'phase_filter_demolished', 'design_option')}
    return rep


# ---------------------------------------------------------------------------------------------------------------- compact form (viewer / panel)
_STYLE_KEYS = ('proj_weight', 'proj_color', 'proj_pattern', 'cut_weight', 'cut_color', 'cut_pattern', 'surf_fg_pattern', 'surf_fg_color', 'surf_bg_pattern', 'surf_bg_color',
               'cut_fg_pattern', 'cut_fg_color', 'cut_bg_pattern', 'cut_bg_color', 'surf_fg_visible', 'surf_bg_visible', 'cut_fg_visible', 'cut_bg_visible', 'halftone', 'transparency', 'detail_level')


def _style(row_proj, row_cut, ov):
    """one deduplicated style: resolved lines + the fill members the view overrides (None = not overridden, the material decides)"""
    def fill(kind):
        pat, rgb = ov.get(kind + '_pattern'), ov.get(kind + '_color')
        vis = ov.get(kind + '_visible')
        if pat is None and rgb is None and vis is None: return None
        return {'pattern': pat, 'rgb': rgb, 'visible': vis is not False}
    return {'proj': row_proj, 'cut': row_cut, 'surf_fg': fill('surf_fg'), 'surf_bg': fill('surf_bg'), 'cut_fg': fill('cut_fg'), 'cut_bg': fill('cut_bg'),
            'halftone': bool(ov.get('halftone')), 'transparency': ov.get('transparency', 0), 'detail_level': ov.get('detail_level')}


def fill_pattern_table(doc):
    out = {}
    for pid, p in (doc.get('fill_patterns') or {}).items():
        out[str(pid)] = {'name': p.get('name'), 'kind': 'model' if p.get('target') == 1 else 'drafting', 'solid': bool(p.get('solid')), 'orientation': p.get('orientation'),
                         'lines': [{'angle': g['angle'], 'origin': g['origin'], 'shift': g['shift'], 'offset': g['offset'], 'dashes': g.get('segments') or []} for g in p.get('grids') or []]}
    return out


def material_table(dec):
    try:
        import rvt_materials
        mt = rvt_materials.material_table(dec.f.fn)
    except Exception: return {}
    out = {}
    for mid, m in mt.items():
        sp, cp = m.get('surface_pattern') or {}, m.get('cut_pattern') or {}
        out[str(mid)] = {'name': m.get('name'), 'rgb': m.get('color'), 'transparency': m.get('transparency'),
                         'surface': {'pattern': sp.get('id'), 'rgb': sp.get('color'), 'bg_pattern': sp.get('background_id'), 'bg_rgb': sp.get('background_color')},
                         'cut': {'pattern': cp.get('id'), 'rgb': cp.get('color'), 'bg_pattern': cp.get('background_id'), 'bg_rgb': cp.get('background_color')}}
    return out


def compact_view(dec, doc, vid, vis=None, full=False):
    """Compact graphics resolution: styles (deduplicated), cat_style {category: style index}, elements {eid: style index} ONLY where the element's style differs
    from its category's (filters / phase / element overrides), hidden element reasons, categories, fill_patterns, materials. `full=True` also lists the
    override source per member (elements_src)."""
    rep = resolve_view(dec, doc, vid, vis=vis, explain=True)
    v = (vis or Visibility(dec, doc)).effective(doc['views'].get(vid) or doc['views'][str(vid)])
    res = Resolver(doc, v, rep['scale'])
    styles, index = [], {}
    def idx(st):
        k = repr(st)
        if k not in index: index[k] = len(styles); styles.append(st)
        return index[k]
    plain = idx(_style(res.line(None, -1, 'proj'), res.line(None, -1, 'cut'), {}))
    cat_style, elements, src, cats_used = {}, {}, {}, {}
    def catstyle(cid):
        if cid not in cat_style:
            ov = res.overrides(None, cid)
            cat_style[cid] = idx(_style(res.line(None, cid, 'proj', None, ov=ov), res.line(None, cid, 'cut', None, ov=ov), ov))
        return cat_style[cid]
    for eid, row in rep['elements'].items():
        cid = row['cat']; cs = catstyle(cid)
        si = idx(_style(row['proj'], row['cut'], row['overrides']))
        if si != cs:
            elements[str(eid)] = si
            if full: src[str(eid)] = row['source']
    cats = {}
    for cid in cat_style:
        c = res._cat(cid); par = c.get('parent', INVALID)
        cats[str(cid)] = {'name': c.get('name'), 'parent': par if par != INVALID else None, 'material': (c.get('proj') or {}).get('material'), 'style': cat_style[cid],
                          'hidden': cid in set(rep['hidden_categories'])}
    out = {k: rep[k] for k in ('view', 'name', 'kind', 'scale', 'template', 'detail_level', 'phase_filter', 'discipline', 'filters', 'hidden_categories', 'excluded', 'excluded_ids', 'links') if k in rep}
    out.update({'styles': styles, 'plain_style': plain, 'cat_style': {str(k): x for k, x in cat_style.items()}, 'elements': elements, 'categories': cats,
                'fill_patterns': fill_pattern_table(doc), 'materials': material_table(dec),
                'notes': {'transparency': 'Revit surface transparency override, 0 (opaque) to 100; honoured for faces in every display style (in Hidden Line faces stay white but become see-through); halftone mixes lines/fills 50% with the background',
                          'fills': 'surf_*/cut_* are the view-level overrides only; null = take the face material (materials[mat].surface / .cut, categories[cat].material as fallback)',
                          'pattern_units': 'drafting patterns in paper feet (x view scale), model patterns in model feet; lines: angle rad, origin [u,v], shift along line, offset between lines, dashes [dash,space,...] empty = continuous'}})
    if full: out['elements_src'] = src
    return out
