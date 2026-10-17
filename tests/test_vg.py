"""Unit tests of the V/G stages (no corpus needed): python -m unittest tests.test_vg"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.vg import template as T, groups as G
from rvtsheets.vg.resolve import _layers
from rvtsheets.style import Resolver


class Template(unittest.TestCase):
    def test_controls(self):
        tpl = {'template': True, 'non_propagated_template_params': [-1005162, -1012103]}
        self.assertFalse(T.controls(tpl, 'view_range')); self.assertFalse(T.controls(tpl, 'phase_filter'))
        self.assertTrue(T.controls(tpl, 'filters')); self.assertTrue(T.controls(tpl, 'model'))
        self.assertFalse(T.controls(None, 'model'))

    def test_template_of(self):
        V = {1: {'template': True}, 2: {'template': False}}
        self.assertEqual(T.template_of(V, {'view_template': 1}), V[1])
        self.assertIsNone(T.template_of(V, {'view_template': 2})); self.assertIsNone(T.template_of(V, {'view_template': -1}))

    def test_group_partition(self):
        v = {'draw_filters': [{'m_categoryIds': [-2000011, -2000220], 'm_modelsExcluded': 0}], 'category_overrides': {-2000011: {'halftone': True}, -2000220: {'transparency': 5}}}
        self.assertEqual(G.value(v, 'model')['hidden'], [-2000011]); self.assertEqual(G.value(v, 'annotation')['hidden'], [-2000220])
        self.assertIn(-2000011, G.value(v, 'model')['overrides'])


class Layers(unittest.TestCase):
    def test_order(self):
        doc = {'categories': {-2000011: {'parent': -1}, -2000012: {'parent': -2000011}}, 'gstyles': {}}
        v = {'category_overrides': {-2000011: {'proj_weight': 3, 'halftone': True}, -2000012: {'proj_weight': 4}}, 'element_overrides': {7: {'proj_color': [1, 2, 3]}}}
        r = Resolver(doc, v, 100)
        m, s = _layers(r, v, 7, -2000012, [{'proj_weight': 5, 'proj_color': [9, 9, 9]}, {'proj_weight': 6}], [10, 11], None)
        self.assertEqual(m['proj_weight'], 5)          # earlier filter wins over later, filters over category
        self.assertEqual(m['proj_color'], [1, 2, 3])   # element override wins over filter
        self.assertTrue(m['halftone']); self.assertEqual(s['halftone'], 'category:-2000011'); self.assertEqual(s['proj_weight'], 'filter:10')


if __name__ == '__main__': unittest.main()


class Links(unittest.TestCase):
    def test_view_links(self):
        from rvtsheets.vg import links as L
        class F:
            byid = {1: 1}
            @staticmethod
            def eid(x): return x
            def recs(self, c): return [{'id': 10}, {'id': 11}] if c == 'RvtLinkSymbol' else []
        fl = {'m_pRvtLinkOverrides': {'m_invisibleSet': [10], 'm_halftoneSet': [10, 11], 'm_underlaySet': [], 'm_displaySettingsMap': [
            {'first': 11, 'second': {'m_overallHLE': 2, 'm_modelHLE': 2, 'm_graphicSettingsMap': [{'first': {'m_id64': -2000011}, 'second': {'m_bVisible': 0, 'm_bHalftone': 1}}], 'm_linkedView': {'m_id64': -1}}}]}}
        r = L.view_links(F(), fl)
        self.assertFalse(r[10]['visible']); self.assertTrue(r[11]['visible']); self.assertTrue(r[11]['halftone'])
        self.assertEqual(r[11]['custom']['overall'], 'custom'); self.assertEqual(r[11]['custom']['categories'][-2000011], {'visible': False, 'halftone': True, 'transparency': 0})
        self.assertIsNone(r[10]['custom'])
