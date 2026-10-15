"""Evaluate ParameterFilterElement rule trees (decode.Decoder._rule_tree) on elements, using the reader's per-element parameter
values (rvt_params: {name: value}). Unknown parameters make a rule false (Revit: elements without the parameter do not pass)."""
from .reader import INVALID


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
        if name in pe: return pe[name]
        # type parameters
        return None

    def rule_ok(self, eid, r):
        if r is None: return True
        if 'op' in r:
            ch = [self.rule_ok(eid, c) for c in r.get('children') or []]
            op = r['op']
            res = any(ch) if op.startswith('LogicalOr') else all(ch)
            return (not res) if r.get('inverted') else res
        cls = r.get('rule') or ''
        if cls == 'FilterInverseRule': return not self.rule_ok(eid, r.get('inner'))
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
