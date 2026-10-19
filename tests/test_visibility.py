"""Unit tests of phase status, design options, worksets and template application in rvtsheets.visibility (no corpus)."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.visibility import Visibility
from rvtsheets.reader import INVALID


def mk(**kw):
    v = Visibility.__new__(Visibility)
    v.phase_index = {10: 0, 11: 1, 12: 2}
    v.doc = {'views': {}}
    for k, x in kw.items(): setattr(v, k, x)
    return v


class Phase(unittest.TestCase):
    def st(self, c, d, p):
        return mk().phase_status({'created': c, 'demolished': d}, p)

    def test_status(self):
        self.assertEqual(self.st(11, INVALID, 11), 'new'); self.assertEqual(self.st(10, INVALID, 11), 'existing')
        self.assertEqual(self.st(10, 11, 11), 'demolished'); self.assertEqual(self.st(11, 11, 11), 'temporary')
        self.assertEqual(self.st(10, 10, 11), 'past'); self.assertEqual(self.st(12, INVALID, 11), 'future')

    def test_unphased(self):
        self.assertIsNone(self.st(INVALID, INVALID, 11)); self.assertIsNone(self.st(10, INVALID, INVALID)); self.assertIsNone(self.st(99, INVALID, 11))


class DesignOptions(unittest.TestCase):
    def test_primary_and_choice(self):
        v = mk(primary_options={1, 3}, option_set={1: 100, 2: 100, 3: 200, 4: 200})
        self.assertEqual(v.shown_options({}), {1, 3})
        self.assertEqual(v.shown_options({'design_options': [(100, 2)]}), {2, 3})          # the view picks option 2 of set 100
        self.assertEqual(v.shown_options({'design_options': [(100, 2), (200, 4)]}), {2, 4})
        self.assertEqual(v.shown_options({'design_options': [(200, INVALID)]}), {1})       # no option chosen for set 200: nothing of it shown


class Worksets(unittest.TestCase):
    def test_hidden(self):
        v = mk(_wsx=({1: 5, 2: 6, 3: 7}, {5: 'A', 6: 'B', 7: 'C'}, {'C'}))
        vw = {'workset_vis': {'A': 0, 'B': 1}}
        self.assertTrue(v.workset_hidden(vw, 1)); self.assertFalse(v.workset_hidden(vw, 2))
        self.assertTrue(v.workset_hidden(vw, 3))                    # not listed in the view: the workset's default visibility
        self.assertFalse(v.workset_hidden({'workset_vis': {'C': 1}}, 3)); self.assertFalse(v.workset_hidden(vw, 99))
        self.assertFalse(mk(_wsx=None).workset_hidden(vw, 1))


class Effective(unittest.TestCase):
    def test_template_copies_controlled_groups_only(self):
        tpl = {'template': True, 'non_propagated_template_params': [-1011002], 'filters': ['T'], 'detail_level': 3, 'phase_filter': 77, 'discipline': 2,
               'draw_filters': [{'m_categoryIds': [1]}], 'category_overrides': {1: {}}}
        v = mk(); v.doc = {'views': {5: tpl}}
        w = v.effective({'view_template': 5, 'filters': ['V'], 'detail_level': 1, 'phase_filter': 1, 'discipline': 1})
        self.assertEqual(w['filters'], ['T']); self.assertEqual(w['phase_filter'], 77); self.assertEqual(w['discipline'], 2)
        self.assertEqual(w['detail_level'], 1)                      # excluded from the template: the view keeps its own
        self.assertEqual(w['draw_filters'], tpl['draw_filters'])
        self.assertEqual(v.effective({'view_template': -1, 'detail_level': 1})['detail_level'], 1)

    def test_vg_not_copied_when_a_tab_is_excluded(self):
        tpl = {'template': True, 'non_propagated_template_params': [-1006962], 'draw_filters': [{'m_categoryIds': [1]}], 'category_overrides': {1: {}}}
        v = mk(); v.doc = {'views': {5: tpl}}
        w = v.effective({'view_template': 5, 'draw_filters': [], 'category_overrides': {}})
        self.assertEqual(w['draw_filters'], [])


if __name__ == '__main__': unittest.main()
