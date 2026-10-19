"""Stage 9: linked models (RvtLinkInstance) in a view. Decodes Link types / instances and the per-view RevitLinkGraphicsSettings
(DBView.m_pRvtLinkOverrides: invisible / halftone / underlay sets keyed by LINK TYPE id (RvtLinkSymbol), m_displaySettingsMap = custom display
settings per link type: per tab (model, annotation, import, view filter, workset, phase, phase filter, discipline, detail level, view range,
design options, nested links, object styles, color scheme, parts) a mode code *HLE; the mode 1 = by linked view is CONFIRMED by the 2024 vg_links scene (LINKOVR ByLinkView + LinkedViewId 356 = overallHLE 1 + m_linkedView 356); 0 = by host view, 2 = custom by elimination).
Revit never lists RvtLinkInstance elements in FilteredElementCollector(doc, viewId) (0 of 1035 view/link pairs in Snowdon Structural, rst_basic): the
settings decide only whether the link's own content is drawn (needs the linked document, see FEATURE-AUDIT)."""
from ..reader import INVALID, ob, path

MODE = {0: 'by_host', 1: 'by_linked', 2: 'custom'}
TABS = ('model', 'annotation', 'import', 'viewFilter', 'worksets', 'phase', 'phaseFilter', 'discipline', 'detailLevel', 'viewRange', 'designOptions', 'nestedLinks', 'objectStyles', 'colorScheme', 'partsVisibility', 'analyticalModel')


def link_types(f):
    """{symbol id: {'name', 'path'}} of the file's Revit link types"""
    out = {}
    for r in f.recs('RvtLinkSymbol'):
        fl = r['fields']
        out[r['id']] = {'name': path(fl, 'm_symbolInfo', 'm_name'),
                        'path': path(ob(fl.get('m_otherDocModelLocation')) or {}, 'm_lastKnownModelPath', 'm_path'), 'attachment': bool(fl.get('m_isAttachment'))}
    return out


def link_instances(f):
    """{instance id: {'symbol', 'transform' (3x3 rows + origin)}}"""
    out = {}
    for r in f.recs('RvtLinkInstance'):
        ii = ob(r['fields'].get('m_pInstanceInfo')) or {}
        trf = ii.get('m_Trf') or {}
        out[r['id']] = {'symbol': f.eid(ii.get('m_symbolId')), 'rot': trf.get('m_3x3'), 'origin': trf.get('m_or')}
    return out


def _custom(f, sec):
    d = {'linked_view': f.eid(path(sec, 'm_linkedView', 'm_id64')) if path(sec, 'm_linkedView', 'm_id64') is not None else INVALID,
         'phase': f.eid(path(sec, 'm_phase', 'm_id64')), 'phase_filter': f.eid(path(sec, 'm_phaseFilter', 'm_id64')),
         'discipline': sec.get('m_discipline'), 'detail_level': sec.get('m_detailLevel'), 'parts_visibility': sec.get('m_partsVisibility'),
         'overall': MODE.get(sec.get('m_overallHLE'), sec.get('m_overallHLE')),
         'modes': {t: MODE.get(sec.get('m_%sHLE' % t), sec.get('m_%sHLE' % t)) for t in TABS if 'm_%sHLE' % t in sec},
         'excluded': {k: bool(sec.get('m_%sExcluded' % k)) for k in ('models', 'annotations', 'analyticalModels', 'imports')},
         'categories': {}}
    for p in sec.get('m_graphicSettingsMap') or []:
        g = p['second']; cid = f.eid(path(p['first'], 'm_id64'))
        d['categories'][cid] = {'visible': bool(g.get('m_bVisible')), 'halftone': bool(g.get('m_bHalftone')), 'transparency': g.get('m_surfacesTransparency') or 0}
    return d


def view_links(f, fl):
    """per link type id: {'visible', 'halftone', 'underlay', 'custom'|None} for the view record fields fl"""
    lo = path(fl, 'm_pRvtLinkOverrides') or {}
    inv = {f.eid(x) for x in lo.get('m_invisibleSet') or []}; ht = {f.eid(x) for x in lo.get('m_halftoneSet') or []}; un = {f.eid(x) for x in lo.get('m_underlaySet') or []}
    cust = {f.eid(p['first']): _custom(f, p['second']) for p in lo.get('m_displaySettingsMap') or [] if isinstance(p, dict) and 'first' in p}
    inst = {iid: i['symbol'] for iid, i in link_instances(f).items()}
    out = {}
    for sid in f.byid and {r['id'] for r in f.recs('RvtLinkSymbol')}:
        # display settings are keyed by link TYPE id in Snowdon (one instance per type) but by link INSTANCE id when a type has several instances
        # (2024 vg_links scene: key 301595 = instance 2, 'By linked view' of plan 356 = LINKOVR row) : per-instance settings in 'instances'
        out[sid] = {'visible': sid not in inv, 'halftone': sid in ht, 'underlay': sid in un, 'type_custom': cust.get(sid), 'custom': cust.get(sid) or next((c for k, c in cust.items() if inst.get(k) == sid), None),
                    'instances': {k: c for k, c in cust.items() if inst.get(k) == sid}}
    return out
