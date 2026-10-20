import os
"""Evaluate ParameterFilterElement rule trees (decode.Decoder._rule_tree) on elements, using the reader's per-element parameter
values (rvt_params: {name: value}). Unknown parameters make a rule false (Revit: elements without the parameter do not pass)."""
from .reader import INVALID


TYPE_NAME_PARAMS = ('Type Name', 'Family Name')


class FilterEval:
    def __init__(self, dec, doc):
        self.dec = dec; self.doc = doc; self._p = None

    def params(self):
        if self._p is None:
            try: self._p = self.dec.f.params()
            except Exception: self._p = {}
        return self._p

    def value(self, eid, rule):
        pe = (self.params().get(eid) or {}).get('params') or {}
        name = rule.get('param_name')
        for sfx in (('|Double', '|Integer', '|String') if isinstance(name, str) else ()):         # values the reader derives from the record (beam 'z Offset Value' from the cell list) are stored under the typed key and override the plain one (Snowdon framing: 18 -> 165 non-zero)
            if name + sfx in pe and os.environ.get('RVT_TYPED_PARAM', '1') == '1': return pe[name + sfx]
        if name in pe:
            v = pe[name]
            if name == 'Family and Type' and isinstance(v, int):
                # stored as the type's element id: 'Family: Type' text (view types: family = the view family; Snowdon section type 'Working')
                tp = (self.params().get(v) or {}).get('params') or {}
                fam = tp.get('Family Name') or {'DBViewType': ''}.get((self.params().get(v) or {}).get('class'), '')
                return '%s: %s' % (fam, tp.get('Type Name', '')) if fam else tp.get('Type Name', '')
            return v
        # type parameters (Type Name, type mark, dimensions...): the element's type element carries them (Revit filters accept instance and type parameters)
        tid = pe.get('Family and Type')
        if isinstance(tid, int) and name in TYPE_NAME_PARAMS:       # only the naming parameters: a general type fallback made Snowdon's 'NOT' filters match (and hide) 2300 elements Revit lists
            tp = (self.params().get(tid) or {}).get('params') or {}
            if name in tp: return tp[name]
        return None

    def rule_ok(self, eid, r):
        if r is None: return True
        if 'op' in r:
            ch = [self.rule_ok(eid, c) for c in r.get('children') or []]
            op = r['op']
            res = any(ch) if op.startswith('LogicalOr') else all(ch)
            return (not res) if r.get('inverted') else res
        cls = r.get('rule') or ''
        if cls == 'FilterInverseRule':
            inn = r.get('inner')
            # an element that lacks the parameter does not pass the inverse rule either (Snowdon L2: 'Walls - Concrete NOT' must not hide the core walls)
            if inn and 'param_name' in inn and self.value(eid, inn) is None: return False
            return not self.rule_ok(eid, inn)
        v = self.value(eid, r)
        ev = (r.get('evaluator') or '')
        if cls.startswith('HasValue') or ev.startswith('HasValue'): return v not in (None, '')
        if cls.startswith('HasNoValue'): return v in (None, '')
        if v is None: return False
        if cls == 'FilterStringRule' or 'String' in ev:
            a = str(v); b = str(r.get('rulestring', ''))
            if not r.get('casesensitive'): a, b = a.lower(), b.lower()
            if ev.endswith('Equals'): return a == b
            if ev.endswith('Contains'): return b in a
            if ev.endswith('BeginsWith'): return a.startswith(b)
            if ev.endswith('EndsWith'): return a.endswith(b)
            if ev.endswith('GreaterOrEqual'): return a >= b
            if ev.endswith('LessOrEqual'): return a <= b
            if ev.endswith('Greater'): return a > b
            if ev.endswith('Less'): return a < b
            return False
        try: a = float(v); b = float(r.get('rulevalue'))
        except Exception: return False
        eps = float(r.get('epsilon') or 1e-6)
        if ev.endswith('GreaterOrEqual'): return a >= b - eps
        if ev.endswith('LessOrEqual'): return a <= b + eps
        if ev.endswith('Equals'): return abs(a - b) <= eps
        if ev.endswith('Greater'): return a > b + eps
        if ev.endswith('Less'): return a < b - eps
        return False

    def matches(self, f, eid, cat, parent=INVALID):
        if f.get('selection') is not None: return eid in f['selection']
        cats = f.get('categories') or []
        if cat not in cats and parent not in cats: return False
        return self.rule_ok(eid, f.get('rules'))

    def view_filters(self, view, eid, cat, parent=INVALID):
        """-> (visible, [override dicts of matching filters in list order])"""
        ovs = []; visible = True
        for vf in view.get('filters') or []:
            if vf.get('enabled') is False: continue
            f = self.doc['filters'].get(vf['filter'])
            if not f or not self.matches(f, eid, cat, parent): continue
            if not vf.get('visible', True): visible = False
            ovs.append(vf.get('overrides') or {})
        return visible, ovs
