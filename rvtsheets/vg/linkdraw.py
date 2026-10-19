"""Stage 9b: the CONTENT of linked models (RvtLinkInstance) drawn into a host plan view.
A second ViewDrawer runs on the linked document with a copy of the chosen linked view whose frame is re-expressed so that its view coordinates
coincide with the host view's (X_L = R^T X_H, O_L = R^T (O_H - t)); the model prims are added to the host drawing with prim['link'] = instance id.
Which linked view: display mode 'by linked view' = the instance's own linked view; 'by host view' (default) = the linked plan view whose cut plane
is closest to the host's, with the host's view range moved into link coordinates.  Off by default (RVT_LINKS=1): unverified against Revit on
anything but the oracle links scene (2026_vg_links: host view 303735 / linked view 303745, 303755)."""
import os, re, copy
import numpy as np
from . import links as L

MODEL_LAYERS = ('cut', 'cut_fill', 'projection', 'symbolic', 'symbolic_fill', 'surface_fill', 'underlay', 'room_fill')
_DOCS = {}


def _norm(n):
    n = os.path.splitext(os.path.basename(n.replace('\\', '/')))[0].lower()
    return re.sub(r'[^a-z0-9]', '', re.sub(r'^\d+_', '', n))


def resolve_path(host_path, link_path):
    """file of a link type: same folder as the host (any of its sibling names, ignoring corpus number prefixes), then RVT_LINK_DIRS"""
    want = _norm(link_path)
    dirs = [os.path.dirname(os.path.abspath(host_path))] + [d for d in os.environ.get('RVT_LINK_DIRS', '').split(os.pathsep) if d]
    for d in dirs:
        try: names = sorted(os.listdir(d))
        except OSError: continue
        for n in names:
            if n.lower().endswith('.rvt') and _norm(n) == want and os.path.abspath(os.path.join(d, n)) != os.path.abspath(host_path): return os.path.join(d, n)
        # scene files: '2026_vg_links.rte' links 'vg_link_target.rvt' stored as '2026_vg_link_target.rvt'
        for n in names:
            if n.lower().endswith('.rvt') and n.lower().split('_', 1)[-1] == os.path.basename(link_path.replace('\\', '/')).lower() and os.path.abspath(os.path.join(d, n)) != os.path.abspath(host_path): return os.path.join(d, n)
    return None


def _linked(path):
    if path not in _DOCS:
        from ..decode import Decoder
        from ..viewdraw import ViewDrawer
        dec = Decoder(path); doc = dec.doc(); _DOCS[path] = (dec, doc, ViewDrawer(dec, doc))
    return _DOCS[path]


def _R(inst):
    return np.asarray(inst['rot'], float), np.asarray(inst['origin'], float)


def host_to_link_view(v, R, t, base, by_host=False, ev=None):
    """copy of the linked view `base` with the host view v's frame and crop expressed in link coordinates; z fields of the view range are not moved (base's own range)"""
    w = copy.deepcopy(base)
    Rt = R.T
    w['origin'] = (Rt @ (np.asarray(v['origin'], float) - t)).tolist()
    for k in ('right', 'up', 'dir'): w[k] = (Rt @ np.asarray(v[k], float)).tolist()
    c = v.get('crop') or {}
    w['crop'] = copy.deepcopy(c)
    if c.get('basis'):
        w['crop']['origin'] = (Rt @ (np.asarray(c['origin'], float) - t)).tolist()
        w['crop']['basis'] = [(Rt @ np.asarray(b, float)).tolist() for b in c['basis']]
    if by_host:      # by host view: the host's phase, phase filter, detail level and view range (z moved into link coordinates) apply to the link content
        ev = ev or v
        for k in ('phase', 'phase_filter', 'detail_level', 'discipline'):
            if ev.get(k) is not None: w[k] = ev[k]
        if v.get('range'):
            w['range'] = {k: (x - t[2] if isinstance(x, (int, float)) and not isinstance(x, bool) and k in ('cut', 'top', 'bottom', 'depth', 'underlay_top', 'underlay_bottom') and abs(x) < 1e8 else x) for k, x in v['range'].items()}
            w['range']['levels'] = base['range'].get('levels')
    return w


def _pick_view(doc, host_v, tz):
    best = None
    cut = (host_v.get('range') or {}).get('cut')
    for vid, lv in doc['views'].items():
        if lv.get('kind') != 'plan' or lv.get('template') or lv.get('class') != 'DBViewPlan' or not lv.get('range') or lv['range'].get('cut') is None: continue
        d = abs(lv['range']['cut'] + tz - (cut if cut is not None else 0))
        if best is None or d < best[0]: best = (d, vid)
    return best[1] if best else None


def _mix(c):
    from ..style import HALFTONE_MIX
    return [int(round(a + (255 - a) * HALFTONE_MIX)) for a in c]


def _halftone(p):
    """link set to halftone in the view: line and fill colours mixed with white like style.py's element halftone"""
    if isinstance(p.get('style'), dict) and p['style'].get('rgb') and not p['style'].get('halftone'): p['style'] = dict(p['style'], rgb=_mix(p['style']['rgb']), halftone=True)
    for k in ('fill', 'color'):
        c = p.get(k)
        if isinstance(c, (list, tuple)) and len(c) == 3 and all(isinstance(x, (int, float)) for x in c): p[k] = _mix(c)
    return p


def link_prims(drawer, vid, v, d, depth=0):
    """model prims of the visible link instances in host plan view vid (dict v, drawing d); nested links (links of a linked model, RVT_LINK_DEPTH levels,
    default 2) recurse with the linked view copy as the host view: its frame already is the host's, so the nested prims need no further transform"""
    out = []
    host_path = drawer.f.fn
    types = L.link_types(drawer.f); insts = L.link_instances(drawer.f)
    fl = (drawer.f.rec(vid) or {}).get('fields') or {}
    vl = L.view_links(drawer.f, fl)
    for iid, inst in insts.items():
        st = vl.get(inst['symbol'])
        if not st or not st['visible']: continue
        cu = st['instances'].get(iid) or st.get('type_custom')
        path = resolve_path(host_path, types[inst['symbol']]['path'] or types[inst['symbol']]['name']) if host_path else None
        if not path: drawer.stats['link_unresolved'] += 1; continue
        R, t = _R(inst)
        dec, doc, drw = _linked(path)
        lvid = None
        if cu and cu.get('overall') == 'by_linked' and cu.get('linked_view') in doc['views']: lvid = cu['linked_view']
        by_host = lvid is None
        if lvid is None: lvid = _pick_view(doc, v, t[2])
        if lvid is None: continue
        saved = doc['views'][lvid]
        doc['views'][lvid] = host_to_link_view(v, R, t, saved, by_host, drawer.vis.effective(v))
        drw._in_link = True        # viewdraw must not draw the linked model's own links with the wrong frame: they are composed here
        try:
            ld = drw._draw(lvid)
            nested = link_prims(drw, lvid, doc['views'][lvid], ld, depth + 1) if depth + 1 < int(os.environ.get('RVT_LINK_DEPTH', '2')) else []
        finally: doc['views'][lvid] = saved; drw._in_link = False
        nested_ids = {id(x) for x in nested}
        for p in list(ld['prims']) + nested:
            if p.get('layer') not in MODEL_LAYERS: continue
            q = dict(p, link=p.get('link', iid)) if id(p) in nested_ids else dict(p, link=iid)
            if st['halftone']: q = _halftone(q)
            out.append(q)
        drawer.stats['link_instances_drawn'] += 1
    return out
