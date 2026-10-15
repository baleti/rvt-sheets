"""Graphic style resolution for model/annotation drawing in a view.
Order (Revit): element override > view filters (first matching in list order, per member) > category override (sub-category falls back to its parent)
> object style (GStyle of the category: pen, colour, pattern). Halftone / transparency / detail level follow the same order.
Pens: model pens depend on the view scale (pen table columns per scale), annotation pens do not."""
import math
from .decode import FT_MM, SOLID_LINE
from .reader import INVALID

HALFTONE_MIX = 0.5            # Revit halftone default (Manage > Halftone/Underlay 50%) (?)


def pen_mm(doc, pen, scale, annotation=False):
    P = doc.get('pens') or {}
    if pen is None or pen < 1: pen = 1
    if annotation or not P.get('model'):
        tab = P.get('annotation') or [0.1, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0, 2.8, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
        return tab[min(pen, len(tab)) - 1]
    cols = sorted((int(k), v) for k, v in P['model'].items())
    # scale between two table columns: interpolate on log(scale) (?) ; beyond the table: the nearest column
    if scale <= cols[0][0]: return cols[0][1][pen - 1]
    if scale >= cols[-1][0]: return cols[-1][1][pen - 1]
    for (s0, a), (s1, b) in zip(cols, cols[1:]):
        if s0 <= scale <= s1:
            if scale == s0: return a[pen - 1]
            if scale == s1: return b[pen - 1]
            t = (math.log(scale) - math.log(s0)) / (math.log(s1) - math.log(s0))
            return a[pen - 1] + t * (b[pen - 1] - a[pen - 1])
    return cols[-1][1][pen - 1]


class Resolver:
    def __init__(self, doc, view, scale):
        self.doc = doc; self.v = view; self.scale = scale
        self.cats = doc['categories']; self.gs = doc['gstyles']
        self.cat_ov = view.get('category_overrides') or {}
        self.el_ov = view.get('element_overrides') or {}

    def _cat(self, cid):
        return self.cats.get(cid) or self.cats.get(str(cid)) or {}

    def cat_style(self, cid, kind):
        """object style of a category for 'proj' / 'cut' (sub-category: own style if set, else parent)"""
        c = self._cat(cid)
        st = c.get(kind)
        if st is None and c.get('parent', INVALID) != INVALID: st = self._cat(c['parent']).get(kind)
        if st is None and kind == 'cut': return self.cat_style(cid, 'proj')
        return st or {}

    def overrides(self, eid, cid, filters_matched=(), phase_ov=None):
        """merged OverrideGraphicSettings dict for an element: category < phase status (when the phase filter says 'overridden') < filters < element"""
        out = {}
        c = self._cat(cid)
        for src in (self.cat_ov.get(c.get('parent')) if c.get('parent', INVALID) != INVALID else None, self.cat_ov.get(cid), phase_ov):
            if src: out.update(src)
        for fo in reversed(list(filters_matched)):                  # earlier filters win
            if fo: out.update(fo)
        e = self.el_ov.get(eid)
        if e: out.update(e)
        return out

    def line(self, gstyle=None, cid=None, kind='proj', eid=None, annotation=False, ov=None):
        st = self.gs.get(gstyle) or self.gs.get(str(gstyle)) if gstyle is not None else None
        if st and st.get('kind') != kind and kind == 'cut':
            st2 = self.cat_style(st.get('cat'), 'cut'); st = dict(st2, cat=st.get('cat')) if st2 else st
        if not st: st = self.cat_style(cid, kind)
        pen = st.get('pen'); rgb = st.get('color') or [0, 0, 0]; pat = st.get('pattern')
        if pen in (None, -1):
            pen = self.cat_style(st.get('cat', cid), kind).get('pen') or 1
        o = ov or {}
        pen = o.get(kind + '_weight', pen); rgb = o.get(kind + '_color', rgb); pat = o.get(kind + '_pattern', pat)
        w = pen_mm(self.doc, pen, self.scale, annotation)
        dash = None
        if pat not in (None, INVALID, SOLID_LINE):
            lp = self.doc['line_patterns'].get(pat) or self.doc['line_patterns'].get(str(pat))
            if lp: dash = [max(s[1] * FT_MM, 0.0) if s[0] != 2 else 0.01 for s in lp['segments']]
        if o.get('halftone'): rgb = [int(round(a + (255 - a) * HALFTONE_MIX)) for a in rgb]
        return {'w': w, 'rgb': rgb, 'dash': dash, 'pen': pen, 'halftone': bool(o.get('halftone'))}
