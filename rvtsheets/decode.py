"""Stage 1: decode view / sheet related records into the rvt-sheets data model (plain dicts, JSON-serialisable).
Units stay Revit internal (feet, radians) except pens, which are converted to millimetres.
Field meanings marked (?) are hypotheses pending the Revit oracle (oracle/viewdump.cs)."""
import math
from .reader import File, ob, path, names, INVALID

FT_MM = 304.8
NO_COLOR = 0x1000000          # 'not set / by category' marker in colour ints (?)
SOLID_LINE = -3000010         # built-in solid line pattern id (?)


def color(v):
    """Revit colour int (COLORREF 0x00BBGGRR) -> [r, g, b] or None when unset"""
    if v is None: return None
    v = int(v)
    if v & NO_COLOR or v < 0: return None
    return [v & 255, (v >> 8) & 255, (v >> 16) & 255]


def xyz(v):
    v = ob(v)
    if isinstance(v, dict): v = v.get('m_xyz')
    return [float(a) for a in v] if v is not None else None


class Decoder:
    def __init__(self, fn):
        self.f = File(fn)
        self.cat_names = names('category')
        self.param_names = names('param')

    E = property(lambda s: s.f.eid)

    # ------------------------------------------------------------------ graphics resources
    def pens(self):
        r = self.f.rec(2, 'PenWidthTableElem') or next(iter(self.f.recs('PenWidthTableElem')), None)
        t = path(r['fields'], 'm_pPenWidthTable') if r else None
        if not t: return None
        mm = lambda ps: [round(p * FT_MM, 4) for p in ps]
        return {'model': {int(m['m_invertedScale']): mm(m['m_pens']) for m in t.get('m_modelPenInfo', [])},
                'annotation': mm(path(t, 'm_draftPenInfo', 'm_pens') or []),
                'perspective': mm(path(t, 'm_perspectiveModelPenInfo', 'm_pens') or [])}

    def line_patterns(self):
        out = {}
        for r in self.f.recs('LinePatternElem'):
            lp = path(r['fields'], 'm_pLinePattern') or {}
            out[r['id']] = {'name': lp.get('m_name'), 'segments': [[int(s['m_type']), float(s['m_data'])] for s in lp.get('m_segs', [])]}
        return out

    def fill_patterns(self):
        out = {}
        for r in self.f.recs('FillPatternElem'):
            fp = path(r['fields'], 'm_pFillPattern') or {}
            grids = []
            for g in fp.get('m_gridsArr', []):
                g = ob(g)
                grids.append({'angle': g['m_angle'], 'origin': g['m_origin'], 'shift': g['m_deltas'][0], 'offset': g['m_deltas'][1], 'segments': list(g.get('m_segs') or [])})
            out[r['id']] = {'name': fp.get('m_name'), 'target': fp.get('m_fpTarget'), 'orientation': fp.get('m_fpOrientation'), 'scale': fp.get('m_scale'),
                            'solid': not grids, 'grids': grids}
        return out

    def categories(self):
        """object styles: {cat id: {name, parent, type, proj:{pen,color,pattern}, cut:{...}, material}}; built-in ids are negative"""
        cats = {}
        for k, n in self.cat_names.items(): cats[int(k)] = {'name': n, 'parent': INVALID}
        for r in self.f.recs('CategoryElem'):
            c = path(r['fields'], 'm_pCategory') or {}
            cats[r['id']] = {'name': c.get('m_name') or '', 'parent': self.E(c.get('m_parentCategoryId')), 'type': c.get('m_categoryType'), 'flags': c.get('m_flags'),
                             'owner': self.E(r['fields'].get('m_ownerId'))}
        styles = {}
        for r in self.f.recs('GStyleElem'):
            fl = r['fields']; g = path(fl, 'm_pGStyle') or {}
            cid = self.E(fl.get('m_categoryId')); kind = {1: 'proj', 2: 'cut'}.get(fl.get('m_gstyleType'), 'type%s' % fl.get('m_gstyleType'))
            pen = g.get('m_penNumber'); pen = -1 if pen in (None, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF) else pen
            st = {'gstyle': r['id'], 'pen': pen, 'color': color(g.get('m_color')), 'pattern': self.E(g.get('m_linePatternId')),
                  'material': self.E(g.get('m_materialElemId')), 'screen': g.get('m_isScreenSized')}
            styles[r['id']] = dict(st, cat=cid, kind=kind)
            cats.setdefault(cid, {'name': '?', 'parent': INVALID})[kind] = st
        return cats, styles

    def fonts(self):
        out = {}
        for r in self.f.recs('FontElem'):
            ft = path(r['fields'], 'm_pFont') or {}
            out[r['id']] = {'name': ft.get('m_name'), 'size': ft.get('m_size'), 'color': color(ft.get('m_color'))}
        return out

    def text_types(self):
        out = {}
        for c in ('TextNoteAttributes', 'TagNoteAttributes'):
            for r in self.f.recs(c):
                fl = r['fields']; la = fl.get('m_lineAndTextAttr') or {}
                out[r['id']] = {'class': c, 'name': path(fl, 'm_symbolInfo', 'm_name'), 'font': self.E(la.get('m_fontId')), 'cat': self.E(la.get('m_categoryId')),
                                'opaque': la.get('m_background'), 'bold': la.get('m_bBold'), 'italic': la.get('m_bItalic'), 'underline': la.get('m_bUnderline'),
                                'leader_offset': fl.get('m_leaderOffsetSheet')}
        return out

    # ------------------------------------------------------------------ phases, filters
    def phases(self):
        ph = [{'id': r['id'], 'name': r['fields'].get('m_name')} for r in self.f.recs('ProjectPhase')]
        allp = next(iter(self.f.recs('AllProjectPhases')), None)
        order = None
        if allp:
            for k, v in allp['fields'].items():
                if isinstance(v, list) and v and all(self.E(x) in {p['id'] for p in ph} for x in v): order = [self.E(x) for x in v]
        if order: ph.sort(key=lambda p: order.index(p['id']) if p['id'] in order else 1e9)
        self.phase_overrides = {}
        if allp:
            for x in allp['fields'].get('m_arrPhasingOverrides') or []:
                o = ob(x) or {}
                self.phase_overrides[o.get('m_elementOnPhaseStatus')] = self.ogs(o.get('m_oOverrideGraphicSettings')) or {}
        pf = [{'id': r['id'], 'name': r['fields'].get('m_name'), 'default': r['fields'].get('m_bDefault'), 'presentation': r['fields'].get('m_phaseStatusPresentation')}
              for r in self.f.recs('PhaseFilterElem')]
        return ph, pf

    def _rule_tree(self, node):
        """ElementFilter data tree -> {'op': and/or, 'inverted', 'children'} | {'rule': class, 'param', 'evaluator', 'value'}"""
        if not isinstance(node, dict): return None
        cls = self.f.tagname(node.get('ptr')) if 'ptr' in node else None
        o = ob(node)
        if not isinstance(o, dict): return None
        if 'm_filters' in o:
            return {'op': (cls or '').replace('FilterData', ''), 'inverted': o.get('m_inverted'), 'children': [self._rule_tree(x) for x in o['m_filters']]}
        if 'm_rules' in o:
            return {'op': 'params', 'class': cls, 'inverted': o.get('m_inverted'), 'children': [self._rule_tree(x) for x in o['m_rules']]}
        rule = {'rule': cls}
        vp = o.get('m_oValueProvider')
        if vp is not None:
            pid = self.E(path(vp, 'm_parameter')); rule['param'] = pid; rule['param_name'] = self.param_names.get(str(pid))
            rule['elem_or_symbol'] = path(vp, 'm_elemOrSymbol')
        ev = o.get('m_oEvaluator')
        if isinstance(ev, dict): rule['evaluator'] = self.f.tagname(ev.get('ptr'))
        for k in ('m_ruleValue', 'm_ruleString', 'm_epsilon', 'm_caseSensitive'):
            if k in o: rule[k[2:].lower()] = o[k] if not hasattr(o[k], 'real') or isinstance(o[k], (int, float)) else int(o[k])
        if 'm_pInnerRule' in o or 'm_innerRule' in o or 'm_oInnerRule' in o: rule['inner'] = self._rule_tree(o.get('m_pInnerRule') or o.get('m_innerRule') or o.get('m_oInnerRule'))
        rest = {k: v for k, v in o.items() if k not in ('m_oValueProvider', 'm_oEvaluator', 'm_ruleValue', 'm_ruleString', 'm_epsilon', 'm_caseSensitive')}
        if rest: rule['other'] = {k: (v if isinstance(v, (int, float, str)) else repr(v)[:200]) for k, v in rest.items()}
        return rule

    def filters(self):
        out = {}
        for r in self.f.recs('ParameterFilterElement'):
            fl = r['fields']
            out[r['id']] = {'name': fl.get('m_name'), 'categories': [self.E(c) for c in (path(fl, 'm_oCategoryRule', 'm_categories') or [])],
                            'rules': self._rule_tree(fl.get('m_oRuleCombination'))}
        for r in self.f.recs('SelectionFilterElement'):
            fl = r['fields']
            ids = next((v for k, v in fl.items() if isinstance(v, list) and k not in ('m_constrInfo',)), [])
            out[r['id']] = {'name': fl.get('m_name'), 'selection': [self.E(i) for i in ids]}
        return out

    # ------------------------------------------------------------------ overrides
    def ogs(self, o):
        """OverrideGraphicSettings record -> dict of the members that are set"""
        o = ob(o)
        if not isinstance(o, dict): return None
        d = {}
        pen = lambda k: path(o, k, 'm_penNumber')
        for k, name in (('m_oProjPenNumber', 'proj_weight'), ('m_oCutPenNumber', 'cut_weight')):
            v = pen(k)
            if v is not None and int(v) not in (-1, 0xFFFFFFFF, 0): d[name] = int(v)
        for k, name in (('m_oProjPenColor', 'proj_color'), ('m_oCutPenColor', 'cut_color'), ('m_oProjFillColor', 'surf_fg_color'), ('m_oSurfaceBackgroundPatternColorOverrider', 'surf_bg_color'),
                        ('m_oCutFillColor', 'cut_fg_color'), ('m_oCutBackgroundPatternColorOverrider', 'cut_bg_color')):
            c = color(path(o, k, 'm_color'))
            if c is not None: d[name] = c
        for k, name in (('m_oProjLinePattern', 'proj_pattern'), ('m_oCutLinePattern', 'cut_pattern')):
            v = self.E(path(o, k, 'm_linePatternId'))
            if v != INVALID: d[name] = v
        for k, name in (('m_oProjFillPattern', 'surf_fg_pattern'), ('m_oSurfaceBackgroundPatternIdOverrider', 'surf_bg_pattern'), ('m_oCutFillPattern', 'cut_fg_pattern'), ('m_oCutBackgroundPatternIdOverrider', 'cut_bg_pattern')):
            v = self.E(path(o, k, 'm_fillPatternId'))
            if v != INVALID: d[name] = v
        for k, name in (('m_bProjFillPatternVisible', 'surf_fg_visible'), ('m_bSurfaceBackgroundFillPatternVisible', 'surf_bg_visible'), ('m_bCutFillPatternVisible', 'cut_fg_visible'), ('m_bCutBackgroundFillPatternVisible', 'cut_bg_visible')):
            if o.get(k) == 0: d[name] = False
        if o.get('m_bHalftone'): d['halftone'] = True
        t = path(o, 'm_oSurfacesTransparency', 'm_transparency')
        if t: d['transparency'] = int(t)
        if o.get('m_detailLevel'): d['detail_level'] = int(o['m_detailLevel'])
        return d

    def category_overrides(self, go):
        """GraphicOverrides (per-category maps) -> {cat id: {member: value}}"""
        go = ob(go) or {}
        out = {}
        def put(cid, k, v): out.setdefault(self.E(cid), {})[k] = v
        def pairs(lst):
            for p in lst or []:
                if isinstance(p, dict) and 'first' in p: yield p['first'], p['second']
        for fld, kind in (('m_gStylesProj', 'proj'), ('m_gStylesCut', 'cut')):
            for cid, g in pairs(go.get(fld)):
                g = ob(g)
                if isinstance(g, dict):
                    if g.get('m_penNumber') not in (None, -1, 0xFFFFFFFF): put(cid, kind + '_weight', g['m_penNumber'])
                    c = color(g.get('m_color'))
                    if c: put(cid, kind + '_color', c)
                    lp = self.E(g.get('m_linePatternId'))
                    if lp != INVALID: put(cid, kind + '_pattern', lp)
                else: put(cid, kind + '_gstyle_raw', repr(g)[:100])
        for fld, k in (('m_fillPatternsProj', 'surf_fg_pattern'), ('m_fillPatternsCut', 'cut_fg_pattern'), ('m_backgroundFillPatternsProj', 'surf_bg_pattern'), ('m_backgroundFillPatternsCut', 'cut_bg_pattern')):
            for cid, v in pairs(go.get(fld)): put(cid, k, self.E(v))
        for fld, k in (('m_fillColorsProj', 'surf_fg_color'), ('m_fillColorsCut', 'cut_fg_color'), ('m_backgroundFillColorsProj', 'surf_bg_color'), ('m_backgroundFillColorsCut', 'cut_bg_color')):
            for cid, v in pairs(go.get(fld)): put(cid, k, color(v))
        for fld, k in (('m_fillHiddenProj', 'surf_fg_visible'), ('m_fillHiddenCut', 'cut_fg_visible'), ('m_backgroundFillHiddenProj', 'surf_bg_visible'), ('m_backgroundFillHiddenCut', 'cut_bg_visible')):
            for cid, v in pairs(go.get(fld)): put(cid, k, not v)
            for x in go.get(fld) or []:
                if not isinstance(x, dict): put(x, k, False)
        for cid, v in pairs(go.get('m_halftones')): put(cid, 'halftone', bool(v))
        for x in go.get('m_halftones') or []:
            if not isinstance(x, dict): put(x, 'halftone', True)
        for cid, v in pairs(go.get('m_surfacesTransparency')): put(cid, 'transparency', int(v))
        for cid, v in pairs(go.get('m_detailLevels')): put(cid, 'detail_level', int(v))
        return out

    # ------------------------------------------------------------------ views
    VIEW_KIND = {'DBViewPlan': 'plan', 'DBViewSection': 'section', 'DBView3d': '3d', 'DBViewDrafting': 'drafting', 'DBViewSchedule': 'schedule',
                 'DBViewRendering': 'rendering', 'DBViewLegend': 'legend', 'DBViewAnonDrafting': 'drafting', 'DBViewProject': 'project',
                 'DBViewGraphSchedColumn': 'graphical_column_schedule', 'DBViewPanelSchedule': 'panel_schedule', 'DBViewSheet': 'sheet'}

    def _paramset(self, fl):
        out = {}
        for k in ('m_pParamValueSetInt', 'm_pParamValueSetElementId', 'm_pParamValueSetDouble', 'm_pParamValueSetAString'):
            for p in path(fl, k, 'm_paramSet') or []:
                pid = self.E(p.get('m_paramId')); v = p.get('m_value')
                out[pid] = self.E(v) if k.endswith('ElementId') else v
        return out

    def crop(self, viewer_id):
        r = self.f.rec(viewer_id, 'Viewer') or self.f.rec(viewer_id)
        if not r: return None
        fl = r['fields']; bs = fl.get('m_boundedSpace') or {}
        out = {'viewer': viewer_id, 'origin': bs.get('m_orig'), 'basis': bs.get('m_basis'), 'bounds': bs.get('m_boundOffset'), 'active': bs.get('m_boundActive'),
               'crop_active': any(any(a) for a in (bs.get('m_boundActive') or [])[:2]), 'far_clip_active': any((bs.get('m_boundActive') or [[], [], []])[2][:1]), 'on': bs.get('m_isOn'),
               'annotation_crop_active': fl.get('m_bAnnotationCropActive'), 'annotation_offsets': path(fl, 'm_pAnnotationCropOffsets', 'm_leftRightTopBottomOffsets'),
               'shape': fl.get('m_nonRectangularCropAreaCurvesLoops') or [], 'reflected': fl.get('m_bReflected'), 'proj_method': fl.get('m_projMethodType'),
               'target': fl.get('m_targetPos'), 'axis': fl.get('m_axisDir'), 'proj_dist': fl.get('m_projDist'), 'sketch': self.E(fl.get('m_sketchId'))}
        return out

    def view(self, r):
        fl = r['fields']; c = r['class']; E = self.E
        ps = self._paramset(fl)
        sc = fl.get('m_scale')
        v = {'id': r['id'], 'class': c, 'kind': self.VIEW_KIND.get(c, c), 'name': fl.get('m_viewName'), 'template': bool(fl.get('m_isTemplate')),
             'scale': (round(1 / sc) if sc else None), 'origin': fl.get('m_origin'), 'right': fl.get('m_horzDir'), 'up': fl.get('m_vertDir'), 'dir': fl.get('m_viewDir'),
             'view_template': E(fl.get('m_viewTemplateId')), 'view_type': E(fl.get('m_dbViewTypeId')), 'level': E(fl.get('m_genElemId')), 'viewer': E(fl.get('m_viewerId')),
             'drawing': E(fl.get('m_dbDrawingId')), 'primary': E(fl.get('m_primaryViewId')), 'dependents': [E(x) for x in fl.get('m_dependentViewIds') or []],
             'parts_visibility': fl.get('m_partsVisibility'), 'description': fl.get('m_viewDescription'), 'display_mode': fl.get('m_modelDisplayMode'),
             'detail_level': ps.get(-1011002), 'discipline': ps.get(-1005163), 'phase': ps.get(-1012102), 'phase_filter': ps.get(-1012103),
             'params': {str(k): v for k, v in ps.items()}, 'non_propagated_template_params': [E(x) for x in fl.get('m_nonPropagatedTemplateParamIds') or []],
             'sheet_viewports': [E(x) for x in fl.get('m_sheetViewportElemIds') or []]}
        if fl.get('m_sheetNumber') is not None:
            v['kind'] = 'sheet'
            for k in ('m_sheetNumber', 'm_drawnBy', 'm_checkedBy', 'm_designedBy', 'm_approvedBy', 'm_issueDate', 'm_date'):
                if k in fl: v[k[2:]] = fl[k]
        if v['viewer'] != INVALID: v['crop'] = self.crop(v['viewer'])
        # view range (plan views)
        vr = path(fl, 'm_pPlanViewRange2')
        if vr:
            v['range'] = {'offsets': vr.get('m_offsets') or vr.get('m_viewDepthPlaneOffsets'), 'levels': [E(x) for x in vr.get('m_levelIds') or vr.get('m_viewDepthPlaneLevelIds') or []],
                          'cut': fl.get('m_cutPlaneElev'), 'top': fl.get('m_topClipElev'), 'bottom': fl.get('m_bottomClipElev'), 'depth': fl.get('m_levelBelowElev'),
                          'underlay_top': fl.get('m_underlayTop'), 'underlay_bottom': fl.get('m_underlayBottom'), 'underlay_level': E(fl.get('m_idUnderlayLevel')),
                          'plan_view_type': fl.get('m_planViewType')}
        for k in ('m_pCutter', 'm_pViewDepthCutter'):
            pl = path(fl, k, 'm_pPlane')
            if pl: v.setdefault('cutters', {})[k[3:]] = {'origin': pl.get('m_origin'), 'x': pl.get('m_xVec'), 'y': pl.get('m_yVec'), 'back': path(fl, k, 'm_bBackPlaneCut')}
        # visibility / graphics
        dfs = []
        for d in fl.get('m_oaDrawFilters') or []:
            o = ob(d); cls = self.f.tagname(d.get('ptr')) if isinstance(d, dict) else None
            if isinstance(o, dict) and o: dfs.append(dict({k: (v2 if k != 'm_categoryIds' else [E(x) for x in v2]) for k, v2 in o.items() if k != 'm_ccda'}, _class=cls))
            else: dfs.append({'_class': cls})
        v['draw_filters'] = dfs
        v['category_overrides'] = self.category_overrides(fl.get('m_oGraphicOverrides'))
        go = path(fl, 'm_oGraphicOverrides') or {}
        v['host_layers_overridden'] = go.get('m_bHostLayersOverridden')
        v['filters'] = [{'filter': E(path(s, 'm_filterElemId')), 'visible': bool(path(s, 'm_bVisibilityFlag')), 'overrides': self.ogs(path(s, 'm_pOverrideGraphicSettings')),
                         'enabled': path(s, 'm_bEnabled', default=None)} for s in path(fl, 'm_oFilterOverrides', 'm_oaSettings') or []]
        ah = path(fl, 'm_oAdHocOverrides') or {}
        v['element_overrides'] = self._adhoc(ah)
        v['hidden_elements'] = sorted(set([E(x) for x in fl.get('m_explicitlyHiddenElements') or []] + [E(x) for x in path(fl, 'm_oHiddenElementsViewSettings', 'm_hiddenElements') or []]))
        v['draw_order'] = path(fl, 'm_pDetailDrawOrderMgr', 'm_aDrawOrder')
        vd = path(fl, 'm_pViewDisplayMgr') or {}
        v['display'] = {k: ob(vd.get(k)) for k in ('m_model',) if k in vd}
        return v

    def _adhoc(self, ah):
        """element overrides: m_elementMap pairs element -> index into m_oaSettings (?)"""
        out = {}
        sets = [self.ogs(path(s, 'm_pOverrideGraphicSettings') or s) for s in ah.get('m_oaSettings') or []]
        for p in ah.get('m_elementMap') or []:
            if isinstance(p, dict) and 'first' in p:
                k = self.E(p['first']); s = p['second']
                try: out[k] = sets[int(s)]
                except Exception: out[k] = {'raw': repr(s)[:200]}
        return out

    def section_boxes(self):
        """3D view section boxes: ModelClipBox.m_viewer3dId -> Viewer3d.m_dbViewId -> view"""
        v3 = {r['id']: self.E(r['fields'].get('m_dbViewId')) for r in self.f.recs('Viewer3d')}
        out = {}
        for r in self.f.recs('ModelClipBox'):
            fl = r['fields']; bs = fl.get('m_boundedSpace') or {}
            vid = v3.get(self.E(fl.get('m_viewer3dId')))
            if vid is not None:
                out[vid] = {'id': r['id'], 'origin': bs.get('m_orig'), 'basis': bs.get('m_basis'), 'bounds': bs.get('m_boundOffset'), 'active': bs.get('m_boundActive'), 'on': bool(bs.get('m_isOn'))}
        return out

    def views(self):
        out = {}
        for r in self.f.recs_prefix('DBView'):
            if r['class'] in ('DBViewType',) or 'm_viewName' not in r['fields']: continue
            try: out[r['id']] = self.view(r)
            except Exception as ex: out[r['id']] = {'id': r['id'], 'class': r['class'], 'error': repr(ex)}
        for vid, sb in self.section_boxes().items():
            if vid in out: out[vid]['section_box'] = sb
        return out

    def view_types(self):
        out = {}
        for r in self.f.recs('DBViewType', 'DBViewTypeAreaPlan'):
            fl = r['fields']
            out[r['id']] = {'name': path(fl, 'm_symbolInfo', 'm_name'), 'family_idx': fl.get('m_systemFamilyIdx'), 'default_template': self.E(fl.get('m_defaultTemplateId')),
                            'ref_label': fl.get('m_refLabelStr'), 'section_attr': self.E(fl.get('m_sectionAttrId')), 'callout_attr': self.E(fl.get('m_calloutAttrId')), 'elevation_attr': self.E(fl.get('m_elevatnAttrId'))}
        return out

    # ------------------------------------------------------------------ sheets
    def viewport_types(self):
        out = {}
        for r in self.f.recs('ViewportAttributes'):
            fl = r['fields']
            out[r['id']] = {'name': path(fl, 'm_symbolInfo', 'm_name'), 'title_family': self.E(fl.get('m_familyTagId')), 'cat': self.E(fl.get('m_categoryId')),
                            'show_label': fl.get('m_showLabel'), 'show_box': fl.get('m_showBox'), 'show_extension_line': fl.get('m_showExtensionLine')}
        return out

    def sheets(self, views):
        E = self.E
        sheets = {vid: v for vid, v in views.items() if v.get('kind') == 'sheet'}
        for s in sheets.values(): s.update(viewports=[], schedules=[], titleblocks=[], owned=[])
        for r in self.f.recs('Viewport', 'GCSViewport'):
            fl = r['fields']; own = E(fl.get('m_ownerDBViewId'))
            if own in sheets:
                sheets[own]['viewports'].append({'id': r['id'], 'view': E(fl.get('m_dbViewId')), 'offset': fl.get('m_offset'), 'scale': fl.get('m_scale'),
                                                 'label_origin': fl.get('m_labelOrigin'), 'label_length': fl.get('m_labelLength'), 'type': E(fl.get('m_attrId')),
                                                 'orientation': fl.get('m_viewportOrientation'), 'clipping': fl.get('m_clipping'), 'detail_number': fl.get('m_detailNumber'),
                                                 'stretch': fl.get('m_stretchFactor')})
        for r in self.f.recs('ScheduleInstance'):
            fl = r['fields']; own = E(fl.get('m_ownerDBViewId'))
            if own in sheets:
                sheets[own]['schedules'].append({'id': r['id'], 'schedule': E(fl.get('m_scheduleId')), 'origin': xyz(fl.get('origin_XYZ')), 'rotation': fl.get('rotationValue'),
                                                 'internal': E(fl.get('m_internalScheduleId'))})
        for r in self.f.recs('FamilyInstance'):
            fl = r['fields']; own = E(fl.get('m_ownerDBViewId'))
            if own in sheets:
                ii = path(fl, 'm_pInstanceInfo') or {}
                sheets[own]['owned'].append({'id': r['id'], 'symbol': E(ii.get('m_symbolId')), 'transform': ii.get('m_Trf'), 'category': self._cat_of(r['id'])})
        for s in sheets.values():
            s['titleblocks'] = [o for o in s['owned'] if o['category'] == -2000280]
        return sheets

    def _cat_of(self, eid):
        h = self.f.eh.get(eid) or {}
        for k in ('m_categroryId', 'm_categoryId', 'category'):
            if k in h: return self.E(h[k])
        return None

    def titleblock_symbol(self, sid):
        r = self.f.rec(sid, 'FamilySymbol')
        if not r: return None
        fl = r['fields']
        def note(n, kind):
            o = ob(n)
            d = {'kind': kind, 'origin': o.get('m_orig'), 'up': o.get('m_upVec'), 'base': o.get('m_baseVec'), 'height': o.get('m_height'), 'width': o.get('m_lineWidth'),
                 'type': self.E(o.get('m_attrId')), 'flags': o.get('m_flags'), 'nowrap': o.get('m_bNoWrapping')}
            if kind == 'label':
                d['params'] = [{'param': self.E(p.get('m_paramId')), 'name': self.param_names.get(str(self.E(p.get('m_paramId')))), 'sample': p.get('m_sampleText'), 'prefix': p.get('m_prefix'),
                                'suffix': p.get('m_suffix'), 'spaces': p.get('m_leadingSpaces'), 'linebreak': p.get('m_bLeadingLineBreak')} for p in o.get('m_paramDataFormattingArr') or []]
            return d
        return {'id': sid, 'name': path(fl, 'm_symbolInfo', 'm_name'), 'family': self.E(fl.get('m_familyId')), 'outline': path(fl, 'm_outline', 'm_minmax'),
                'labels': [note(n, 'label') for n in fl.get('m_tagNoteData') or []], 'texts': [note(n, 'text') for n in fl.get('m_textNoteData') or []]}

    # ------------------------------------------------------------------ everything
    def doc(self):
        cats, styles = self.categories()
        views = self.views()
        ph, pf = self.phases()
        sheets = self.sheets(views)
        tbs = {}
        for s in sheets.values():
            for t in s['titleblocks']:
                if t['symbol'] not in tbs: tbs[t['symbol']] = self.titleblock_symbol(t['symbol'])
        return {'file': self.f.fn, 'idbits': self.f.idbits, 'pens': self.pens(), 'line_patterns': self.line_patterns(), 'fill_patterns': self.fill_patterns(),
                'categories': cats, 'gstyles': styles, 'phase_overrides': getattr(self, 'phase_overrides', {}), 'fonts': self.fonts(), 'text_types': self.text_types(), 'phases': ph, 'phase_filters': pf,
                'filters': self.filters(), 'view_types': self.view_types(), 'viewport_types': self.viewport_types(), 'views': views,
                'sheets': {k: {kk: vv for kk, vv in v.items() if kk in ('id', 'name', 'sheetNumber', 'viewports', 'schedules', 'titleblocks', 'owned')} for k, v in sheets.items()},
                'titleblock_symbols': tbs}
