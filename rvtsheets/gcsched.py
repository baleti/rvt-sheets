"""Graphical column schedule (DBViewGraphSchedColumn): a table of columns per page (m_columnsPerRow cells of m_meshWidth), one cell per grid intersection
(m_visGridIntPntArr, in the view's order), level lines at their true elevations across the page, level names/elevations in a side strip at both ends,
a 'Column Locations' row at the bottom. The columns' own symbolic graphics are drawn at the view origin by Revit's stored view; every instance is moved into its cell.
Measured against Revit's DXF of rst_basic view 1250040 (gt_views): lines at x 0, 2925, 3000 + 3000 n, right strip double line; page pitch height + heightBetween."""
import os
import numpy as np

FT = 304.8
LEVEL_CAT = -2000240
COLUMN_CAT = -2001330


def _off(mm):
    return '(%d)' % round(mm) if abs(mm) >= 0.5 else ''


def _translate(p, dx, dy):
    q = dict(p)
    if 'pts' in q: q['pts'] = [[x + dx, y + dy] + list(rest) for x, y, *rest in q['pts']]
    if 'segs' in q: q['segs'] = [[[x + dx, y + dy] + list(rest) for x, y, *rest in sg] for sg in q['segs']]
    if 'loops' in q: q['loops'] = [[[x + dx, y + dy] + list(rest) for x, y, *rest in lp] for lp in q['loops']]
    if 'origin' in q: q['origin'] = [q['origin'][0] + dx, q['origin'][1] + dy] + list(q['origin'][2:])
    if 'anchor' in q and isinstance(q['anchor'], (list, tuple)): q['anchor'] = [q['anchor'][0] + dx, q['anchor'][1] + dy] + list(q['anchor'][2:])
    return q


def _xs(p):
    if 'pts' in p: return [pt[0] for pt in p['pts']]
    if 'segs' in p: return [pt[0] for sg in p['segs'] for pt in sg]
    if 'loops' in p: return [pt[0] for lp in p['loops'] for pt in lp]
    return []


def _column_box(f, eid):
    """(smaller horizontal extent, z0, z1) of the column's solid in feet"""
    try:
        import rvt_elemmesh as E
        bb = E.element_mesh(f.g, eid).get('bbox')
        d = np.asarray(bb[1], float) - np.asarray(bb[0], float)
        return float(min(d[0], d[1])), float(bb[0][2]), float(bb[1][2])
    except Exception: return None


def _column_fill(vd, f, eid):
    """colour of the column's material surface pattern: solid pattern -> its colour (Metal - Steel 128,64,64), other pattern -> its colour, none -> None"""
    try:
        import collections
        import rvt_elemmesh as E
        mats = vd.materials()
        c = collections.Counter(int(m) for m in (E.element_mesh(f.g, eid).get('mat') or []) if m is not None and int(m) in mats)
        if not c: return None
        sp = (mats[c.most_common(1)[0][0]].get('surface_pattern') or {})
        col = sp.get('color')
        if not (isinstance(col, (list, tuple)) and len(col) >= 3 and sp.get('id') is not None): return None
        pat = vd.doc['fill_patterns'].get(sp['id']) or {}
        return list(col)[:3] if pat.get('solid') else [214, 214, 214]       # a hatched / stippled pattern (cast-in-place concrete) shows as a light grey tone at schedule scale
    except Exception: return None


def rebuild(dr_, f, v, prims, vd=None):
    """prims of the stored drawing -> prims of the schedule table"""
    r = f.rec(v['id']); fl = r['fields'] if r else {}
    cells = fl.get('m_visGridIntPntArr') or []
    if not cells: return prims
    E = f.eid
    per = max(int(fl.get('m_columnsPerRow') or 20), 1)
    sc = v.get('scale') or 100
    mesh = round((fl.get('m_meshWidth') or 0.0984252) * FT * sc, 3); side = round((fl.get('m_sideWidth') or 0.0984252) * FT * sc, 3)
    above = (fl.get('m_heightAbove') or 0.0492126) * FT * sc; below = (fl.get('m_heightBelow') or 0.0984252) * FT * sc; between = (fl.get('m_heightBetween') or 0.0492126) * FT * sc
    # levels: elevation (mm) from the level's own drawn line, names/values from its two text prims
    lev = {}
    for p in prims:
        if p.get('cat') != LEVEL_CAT: continue
        d = lev.setdefault(p['elem'], {'texts': []})
        if p['t'] == 'line' and p.get('part') == 'line' and 'y' not in d: d['y'] = p['pts'][0][1] * FT
        elif p['t'] == 'text': d['texts'].append(p)
    levels = sorted([d for d in lev.values() if 'y' in d and d['texts']], key=lambda d: -d['y'])
    if not levels: return prims
    tmpl = dict(levels[0]['texts'][0]); tmpl['size'] = (fl.get('m_textSize') or 0.0078740157) * sc          # 2.4 mm paper text
    top = levels[0]['y'] + above; bot = levels[-1]['y'] - below; loc = bot + between      # bot = bottom edge of the 'Column Locations' row
    page_h = top - bot; pitch = page_h + between
    # cell label and columns
    names = {}
    def gname(g):
        if g not in names:
            gr = f.rec(g); names[g] = (gr['fields'].get('m_text') or '') if gr else ''
        return names[g]
    cols = []
    for c in cells:
        g0, g1 = E(c['m_grid0Id']), E(c['m_grid1Id'])
        cols.append(('%s%s-%s%s' % (gname(g1), _off(c['m_offset1'] * FT), gname(g0), _off(c['m_offset0'] * FT)), [E(x) for x in c['m_columnIdArr']]))
    sym = {}
    for p in prims:
        if p.get('cat') == COLUMN_CAT and p.get('elem') is not None: sym.setdefault(p['elem'], []).append(p)
    out = []
    line = {'w': 0.1, 'rgb': [0, 0, 0], 'dash': None, 'pen': 1, 'halftone': False}
    def L(x0, y0, x1, y1, page_y):
        out.append({'t': 'line', 'pts': [[x0 / FT, (y0 + page_y) / FT], [x1 / FT, (y1 + page_y) / FT]], 'style': dict(line), 'layer': 'symbolic', 'paper': False, 'part': 'frame', 'elem': v['id']})
    def T(s, x, y, page_y, halign):
        t = dict(tmpl); t.update({'text': s, 'origin': [x / FT, (y + page_y) / FT], 'halign': halign, 'valign': 0, 'anchor': True, 'elem': v['id'], 'cat': None, 'part': 'text'})
        t.pop('layer', None); t['layer'] = 'text'
        out.append(t)
    npages = (len(cols) + per - 1) // per
    for k in range(npages):
        part = cols[k * per:(k + 1) * per]; n = len(part); py = -k * pitch
        width = side + n * mesh + side
        xr = side + n * mesh                                         # right strip starts here
        for y in [lv['y'] for lv in levels] + [top, bot, loc]: L(0, y, width, y, py)
        for x in [0, side - 75, side] + [side + i * mesh for i in range(1, n + 1)] + [xr + 75]: L(x, bot, x, top, py)
        L(width, bot, width, top, py)
        for x0 in (150, xr + 225):
            for lv in levels:
                names_ = lv['texts']
                if len(names_) >= 2: T(names_[0]['text'], x0, lv['y'] + 472.9, py, 0); T(names_[1]['text'], x0, lv['y'] - 215.1, py, 0)
            T('Column Locations', 150 if x0 == 150 else xr + 225, loc - 215.1, py, 0)
        for j, (lab, ids) in enumerate(part):
            cx = side + j * mesh + mesh / 2
            T(lab, cx, loc - 621.1, py, 1)
            for cid in ids:
                ps = sym.get(cid, [])
                allx = [x for p in ps for x in _xs(p)]
                if not allx: continue
                mx = (min(allx) + max(allx)) / 2
                bb_ = _column_box(f, cid) if vd is not None and os.environ.get('RVT_GCS_FILL', '1') == '1' else None
                col_ = _column_fill(vd, f, cid) if bb_ is not None and bb_[0] * FT >= 100 else None
                if col_:        # the column's profile (smaller horizontal extent of its solid, base to top) carries its material surface pattern colour (Revit DXF: one S-COLS HATCH per column; HSS tubes are hollow rings, not filled here)
                    x0_, x1_ = cx / FT - bb_[0] / 2, cx / FT + bb_[0] / 2; y0_, y1_ = bb_[1] + py / FT, bb_[2] + py / FT
                    out.append({'t': 'fill', 'loops': [[[x0_, y0_], [x1_, y0_], [x1_, y1_], [x0_, y1_]]], 'color': col_, 'elem': cid, 'layer': 'surface_fill'})
                for p in ps:
                    q = _translate(p, cx / FT - mx, py / FT)
                    if isinstance(q.get('style'), dict): q['style'] = dict(q['style'], w=min(q['style'].get('w', 0.18), 0.18))        # Revit's S-COLS lines are the thin default weight
                    out.append(q)
    return out
