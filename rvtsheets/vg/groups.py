"""Canonical value of one V/G setting group of a decoded view dict (for template comparison and per-group merging)."""
import json, os
from ..reader import INVALID

CAT_TYPES = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'category_types.json'))).items()}
TYPE_OF_GROUP = {'model': 'Model', 'annotation': 'Annotation', 'analytical': 'AnalyticalModel'}
EXCLUDED_FLAG = {'model': 'm_modelsExcluded', 'annotation': 'm_annotationsExcluded', 'analytical': 'm_analyticalModelsExcluded', 'import': 'm_importsExcluded'}


def cat_group(cid, cats=None):
    """V/G tab a category belongs to: model / annotation / analytical / import (imported categories are the DWG/DGN import categories)"""
    t = CAT_TYPES.get(cid)
    if t is None and cats:
        par = (cats.get(cid) or {}).get('parent', INVALID)
        t = CAT_TYPES.get(par)
    return {'Model': 'model', 'Annotation': 'annotation', 'AnalyticalModel': 'analytical'}.get(t)


def excluded_set(view):
    """the view's category-exclusion wrapper (first draw filter with m_categoryIds): (hidden category ids, flags)"""
    for d in view.get('draw_filters') or []:
        if d.get('m_categoryIds') is not None:
            return set(d['m_categoryIds']), d
    return set(), {}


def value(view, group, cats=None):
    """canonical (JSON-able) value of the setting group in the view"""
    if group in ('model', 'annotation', 'analytical', 'import'):
        hidden, d = excluded_set(view)
        mine = lambda c: cat_group(c, cats) == group
        ov = {c: o for c, o in (view.get('category_overrides') or {}).items() if mine(c)}
        return {'hidden': sorted(c for c in hidden if mine(c)), 'excluded': d.get(EXCLUDED_FLAG[group]), 'overrides': ov}
    if group == 'filters': return view.get('filters')
    if group == 'scale': return view.get('scale')
    if group == 'detail_level': return view.get('detail_level')
    if group == 'discipline': return view.get('discipline')
    if group == 'phase_filter': return view.get('phase_filter')
    if group == 'view_range': return view.get('range')
    if group == 'display_model': return view.get('display_mode')
    return None


def same(a, b):
    f = lambda x: json.dumps(x, sort_keys=True, default=str)
    return f(a) == f(b)
