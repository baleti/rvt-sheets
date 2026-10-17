"""Stage 1: view templates and the template-controlled parameter list (TPLCTL).

Facts (Revit 2020/2024/2026 oracle, TPLCTL rows of gt_views + rosetta view_h_template base/var):
* A template's controlled set = (parameters applicable to the view family) minus the template's m_nonPropagatedTemplateParamIds. Revit's TPLCTL
  'noncontrolled' list equals the decoded m_nonPropagatedTemplateParamIds exactly for every template of the corpus.
* Applying a template COPIES its controlled settings into the view record (the rosetta var file shows discipline, phase filter, view range,
  V/G sets rewritten on the view), so the stored view values already are the effective ones; a parameter the template does not control keeps the
  view's own stored value (it may differ from the template's).
"""
from ..reader import INVALID

# V/G and view parameter ids (BuiltInParameter, rvt-research param_names.json) -> the setting group they govern
VG_MODEL, VG_ANNOTATION, VG_IMPORT, VG_FILTERS, VG_LINKS, VG_DESIGN_OPTIONS, VG_ANALYTICAL = -1006961, -1006962, -1006963, -1006964, -1006965, -1006966, -1006967
SCALE_IDS = (-1005152, -1005151, -1005150)
GROUP_PARAMS = {
    'model': (VG_MODEL,), 'annotation': (VG_ANNOTATION,), 'import': (VG_IMPORT,), 'analytical': (VG_ANALYTICAL,),
    'filters': (VG_FILTERS,), 'links': (VG_LINKS,), 'design_options': (VG_DESIGN_OPTIONS,),
    'scale': SCALE_IDS, 'detail_level': (-1011002,), 'parts_visibility': (-1011003,), 'discipline': (-1005163,), 'phase_filter': (-1012103,),
    'view_range': (-1005162,), 'orientation': (-1005168,), 'display_model': (-1005161,), 'model_display': (-1005131,), 'shadows': (-1005132,),
    'lighting': (-1005133,), 'background': (-1005135,), 'exposure': (-1005137,), 'far_clip': (-1005123,), 'depth_clip': (-1005181,),
    'hidden_lines': (-1154613,), 'sketchy': (-1154615,), 'underlay_orientation': (-1005177,), 'color_scheme': (-1005148, -1005183), 'cropping': (-1005136,),
}
# always excluded from templates in every Revit version (TPLCTL noncontrolled in all rows)
ALWAYS_EXCLUDED = (-1133900, -1005183, -1005177, -1005148)


def template_of(doc_views, view):
    t = view.get('view_template')
    if t in (None, INVALID, -1): return None
    tv = doc_views.get(t) or doc_views.get(str(t))
    return tv if tv and tv.get('template') else None


def excluded_ids(tpl):
    return set(tpl.get('non_propagated_template_params') or [])


def controls(tpl, group):
    """does template tpl control the setting group (every id of the group present = not excluded)"""
    if tpl is None: return False
    return not any(p in excluded_ids(tpl) for p in GROUP_PARAMS[group])


def controlled_groups(tpl):
    return [g for g in GROUP_PARAMS if controls(tpl, g)]
