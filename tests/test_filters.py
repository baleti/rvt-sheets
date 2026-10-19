"""Unit tests of filter rule evaluation (stage 3), no corpus: python -m unittest tests.test_filters"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.filters import FilterEval


class FakeFile:
    def __init__(self, p): self.p = p
    def params(self): return self.p


class Dec:
    def __init__(self, p): self.f = FakeFile(p)


def ev(params, filters=None):
    return FilterEval(Dec(params), {'filters': filters or {}})


def S(name, op, s, cs=False): return {'rule': 'FilterStringRule', 'param_name': name, 'evaluator': 'FilterStringContains'.replace('Contains', op), 'rulestring': s, 'casesensitive': cs}
def N(name, op, v, eps=1e-6): return {'rule': 'FilterNumericValueRule', 'param_name': name, 'evaluator': 'FilterNumeric' + op, 'rulevalue': v, 'epsilon': eps}


class Rules(unittest.TestCase):
    P = {1: {'params': {'Mark': 'Door-A1', 'Width': 3.0, 'Family and Type': 9}}, 2: {'params': {'Mark': 'wall'}}, 9: {'class': 'FamilySymbol', 'params': {'Type Name': 'Single', 'Family Name': 'Door'}}}

    def test_string(self):
        e = ev(self.P)
        self.assertTrue(e.rule_ok(1, S('Mark', 'Contains', 'door')))                 # case-insensitive by default
        self.assertFalse(e.rule_ok(1, S('Mark', 'Contains', 'door', cs=True)))
        self.assertTrue(e.rule_ok(1, S('Mark', 'BeginsWith', 'Door'))); self.assertTrue(e.rule_ok(1, S('Mark', 'EndsWith', 'a1')))
        self.assertTrue(e.rule_ok(1, S('Mark', 'Equals', 'door-a1'))); self.assertFalse(e.rule_ok(2, S('Mark', 'Equals', 'door-a1')))

    def test_missing_parameter_fails(self):
        e = ev(self.P)
        self.assertFalse(e.rule_ok(2, S('Nope', 'Equals', 'x')))
        inv = {'rule': 'FilterInverseRule', 'inner': S('Nope', 'Equals', 'x')}
        self.assertFalse(e.rule_ok(2, inv))                                          # lacking the parameter does not pass the inverse rule
        self.assertTrue(e.rule_ok(2, {'rule': 'FilterInverseRule', 'inner': S('Mark', 'Equals', 'x')}))

    def test_numeric(self):
        e = ev(self.P)
        self.assertTrue(e.rule_ok(1, N('Width', 'Equals', 3.0))); self.assertTrue(e.rule_ok(1, N('Width', 'GreaterOrEqual', 3.0)))
        self.assertFalse(e.rule_ok(1, N('Width', 'Greater', 3.0))); self.assertTrue(e.rule_ok(1, N('Width', 'Less', 3.5)))
        self.assertTrue(e.rule_ok(1, N('Width', 'Equals', 3.0005, eps=1e-3)))

    def test_type_name_fallback_and_family_and_type(self):
        e = ev(self.P)
        self.assertTrue(e.rule_ok(1, S('Type Name', 'Equals', 'single')))
        self.assertEqual(e.value(1, {'param_name': 'Family and Type'}), 'Door: Single')

    def test_has_value(self):
        e = ev(self.P)
        self.assertTrue(e.rule_ok(1, {'rule': 'HasValueRule', 'param_name': 'Mark'})); self.assertFalse(e.rule_ok(1, {'rule': 'HasValueRule', 'param_name': 'Nope'}))
        self.assertTrue(e.rule_ok(1, {'rule': 'HasNoValueRule', 'param_name': 'Nope'}))

    def test_nested(self):
        e = ev(self.P)
        a, b = S('Mark', 'Contains', 'door'), N('Width', 'Greater', 5)
        self.assertFalse(e.rule_ok(1, {'op': 'LogicalAnd', 'children': [a, b]})); self.assertTrue(e.rule_ok(1, {'op': 'LogicalOr', 'children': [a, b]}))
        self.assertTrue(e.rule_ok(1, {'op': 'LogicalAnd', 'inverted': True, 'children': [a, b]}))
        self.assertTrue(e.rule_ok(1, None))


class Matching(unittest.TestCase):
    def test_category_parent_and_selection(self):
        e = ev(Rules.P)
        f = {'categories': [-2000023], 'rules': S('Mark', 'Contains', 'door')}
        self.assertTrue(e.matches(f, 1, -2000023)); self.assertTrue(e.matches(f, 1, -2000999, parent=-2000023)); self.assertFalse(e.matches(f, 1, -2000011))
        self.assertTrue(e.matches({'selection': [1]}, 1, 0)); self.assertFalse(e.matches({'selection': [1]}, 2, 0))

    def test_view_filters_order_visibility_disabled(self):
        F = {10: {'categories': [5], 'rules': None}, 11: {'categories': [5], 'rules': None}, 12: {'categories': [5], 'rules': None}}
        e = ev({}, F)
        view = {'filters': [{'filter': 10, 'overrides': {'a': 1}}, {'filter': 11, 'visible': False, 'overrides': {'a': 2}}, {'filter': 12, 'enabled': False, 'overrides': {'a': 3}}]}
        vis, ovs = e.view_filters(view, 1, 5)
        self.assertFalse(vis); self.assertEqual(ovs, [{'a': 1}, {'a': 2}])


if __name__ == '__main__': unittest.main()
