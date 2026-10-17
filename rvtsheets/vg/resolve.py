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
    if explain:
        import collections
        rep['excluded'] = dict(collections.Counter(why.values()))
        rep['excluded_ids'] = {k: w for k, w in why.items() if w in ('filter_hidden', 'hidden_element', 'category_hidden', 'phase_filter_new', 'phase_filter_existing', 'phase_filter_demolished', 'design_option')}
    return rep
