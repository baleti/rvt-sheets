"""Synthetic characterisation tests for linked-model V/G settings."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.reader import INVALID
from rvtsheets.vg import links as L


class FakeF:
    def __init__(self, records=None):
        self.records = records or {}
        self.byid = {1: 1} if any(self.records.values()) else {}

    def recs(self, cls):
        return self.records.get(cls, [])

    @staticmethod
    def eid(x):
        if x is None:
            return INVALID
        return x if isinstance(x, int) else int(re.search(r'-?\d+', x).group())


def pointer(obj):
    return {'ptr': 1, 'obj': obj}


def record(eid, **fields):
    return {'id': eid, 'fields': fields}


def reader():
    return FakeF({
        'RvtLinkSymbol': [
            record(10, m_symbolInfo=pointer({'m_name': 'Architecture'}),
                   m_otherDocModelLocation=pointer({
                       'm_lastKnownModelPath': pointer({'m_path': 'synthetic.rvt'})}),
                   m_isAttachment=1),
            record(20, m_symbolInfo=pointer({'m_name': 'Structure'}))],
        'RvtLinkInstance': [
            record(101, m_pInstanceInfo=pointer({
                'm_symbolId': 'EID(10)',
                'm_Trf': {'m_3x3': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                          'm_or': [0, 0, 0]}})),
            record(102, m_pInstanceInfo=pointer({
                'm_symbolId': 10,
                'm_Trf': {'m_3x3': [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                          'm_or': [4, 5, 6]}})),
            record(103)]})


def view(**overrides):
    return L.view_links(reader(), {'m_pRvtLinkOverrides': pointer(overrides)})


def setting(key, mode):
    return {'first': key, 'second': {'m_overallHLE': mode}}


class Constants(unittest.TestCase):
    def test_mode(self):
        self.assertEqual(L.MODE, {0: 'by_host', 1: 'by_linked', 2: 'custom'})

    def test_tabs(self):
        self.assertEqual(L.TABS, (
            'model', 'annotation', 'import', 'viewFilter', 'worksets', 'phase',
            'phaseFilter', 'discipline', 'detailLevel', 'viewRange',
            'designOptions', 'nestedLinks', 'objectStyles', 'colorScheme',
            'partsVisibility', 'analyticalModel'))


class Links(unittest.TestCase):
    def test_types(self):
        self.assertEqual(L.link_types(reader()), {
            10: {'name': 'Architecture', 'path': 'synthetic.rvt', 'attachment': True},
            20: {'name': 'Structure', 'path': None, 'attachment': False}})

    def test_empty_types_and_instances(self):
        self.assertEqual(L.link_types(FakeF()), {})
        self.assertEqual(L.link_instances(FakeF()), {})

    def test_instances(self):
        self.assertEqual(L.link_instances(reader()), {
            101: {'symbol': 10, 'rot': [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 'origin': [0, 0, 0]},
            102: {'symbol': 10, 'rot': [[0, -1, 0], [1, 0, 0], [0, 0, 1]], 'origin': [4, 5, 6]},
            103: {'symbol': INVALID, 'rot': None, 'origin': None}})

    def test_missing_transform(self):
        f = FakeF({'RvtLinkInstance': [record(1, m_pInstanceInfo=pointer({'m_symbolId': 10}))]})
        self.assertEqual(L.link_instances(f), {1: {'symbol': 10, 'rot': None, 'origin': None}})


class Custom(unittest.TestCase):
    def test_missing_keys(self):
        self.assertEqual(L._custom(FakeF(), {}), {
            'linked_view': INVALID, 'phase': INVALID, 'phase_filter': INVALID,
            'discipline': None, 'detail_level': None, 'parts_visibility': None,
            'overall': None, 'modes': {},
            'excluded': {'models': False, 'annotations': False, 'analyticalModels': False, 'imports': False},
            'categories': {}})

    def check_modes(self, code, expected):
        sec = {'m_%sHLE' % tab: code for tab in L.TABS}
        sec['m_overallHLE'] = code
        result = L._custom(FakeF(), sec)
        self.assertEqual(result['overall'], expected)
        self.assertEqual(result['modes'], dict.fromkeys(L.TABS, expected))

    def test_host_modes(self):
        self.check_modes(0, 'by_host')

    def test_linked_modes(self):
        self.check_modes(1, 'by_linked')

    def test_custom_modes(self):
        self.check_modes(2, 'custom')

    def test_unknown_modes(self):
        self.check_modes(97, 97)

    def test_explicit_none_mode(self):
        self.assertEqual(L._custom(FakeF(), {'m_modelHLE': None})['modes'], {'model': None})

    def test_ids_and_scalar_settings(self):
        result = L._custom(FakeF(), {
            'm_linkedView': pointer({'m_id64': 'EID(356)'}),
            'm_phase': pointer({'m_id64': 42}),
            'm_phaseFilter': pointer({'m_id64': 'EID(43)'}),
            'm_discipline': 3, 'm_detailLevel': 2, 'm_partsVisibility': 1})
        for key, expected in {'linked_view': 356, 'phase': 42, 'phase_filter': 43,
                              'discipline': 3, 'detail_level': 2, 'parts_visibility': 1}.items():
            self.assertEqual(result[key], expected)

    def test_excluded_flags(self):
        result = L._custom(FakeF(), {'m_modelsExcluded': 1, 'm_annotationsExcluded': 0,
                                    'm_analyticalModelsExcluded': 'yes', 'm_importsExcluded': None})
        self.assertEqual(result['excluded'], {
            'models': True, 'annotations': False, 'analyticalModels': True, 'imports': False})

    def test_categories(self):
        result = L._custom(FakeF(), {'m_graphicSettingsMap': [
            {'first': pointer({'m_id64': 'EID(-2000011)'}),
             'second': {'m_bVisible': 1, 'm_bHalftone': 0, 'm_surfacesTransparency': 35}},
            {'first': {'m_id64': -2000012}, 'second': {'m_bVisible': 0, 'm_bHalftone': 1}},
            {'first': {'m_id64': -2000013}, 'second': {'m_surfacesTransparency': None}}]})
        self.assertEqual(result['categories'], {
            -2000011: {'visible': True, 'halftone': False, 'transparency': 35},
            -2000012: {'visible': False, 'halftone': True, 'transparency': 0},
            -2000013: {'visible': False, 'halftone': False, 'transparency': 0}})

    def test_null_categories(self):
        self.assertEqual(L._custom(FakeF(), {'m_graphicSettingsMap': None})['categories'], {})


class ViewLinks(unittest.TestCase):
    def test_without_overrides(self):
        default = {'visible': True, 'halftone': False, 'underlay': False,
                   'type_custom': None, 'custom': None, 'instances': {}}
        self.assertEqual(L.view_links(reader(), {}), {10: default, 20: default})

    def test_sets(self):
        result = view(m_invisibleSet=['EID(10)', 999],
                      m_halftoneSet=[10, 'EID(20)'], m_underlaySet=['EID(20)'])
        self.assertEqual(set(result), {10, 20})
        self.assertFalse(result[10]['visible']); self.assertTrue(result[20]['visible'])
        self.assertTrue(result[10]['halftone']); self.assertTrue(result[20]['halftone'])
        self.assertFalse(result[10]['underlay']); self.assertTrue(result[20]['underlay'])

    def test_type_custom(self):
        result = view(m_displaySettingsMap=[setting('EID(20)', 2)])
        expected = L._custom(FakeF(), {'m_overallHLE': 2})
        self.assertEqual(result[20]['type_custom'], expected)
        self.assertEqual(result[20]['custom'], expected)
        self.assertEqual(result[20]['instances'], {})
        self.assertIsNone(result[10]['custom'])

    def test_instance_custom_and_first_match(self):
        result = view(m_displaySettingsMap=[setting('EID(102)', 1), setting(101, 2), setting(999, 0)])
        self.assertIsNone(result[10]['type_custom'])
        self.assertEqual(result[10]['custom']['overall'], 'by_linked')
        self.assertEqual({k: v['overall'] for k, v in result[10]['instances'].items()},
                         {102: 'by_linked', 101: 'custom'})
        self.assertIsNone(result[20]['custom'])
        self.assertEqual(result[20]['instances'], {})

    def test_type_custom_takes_precedence(self):
        result = view(m_displaySettingsMap=[setting(101, 1), setting(10, 0)])
        self.assertEqual(result[10]['custom'], result[10]['type_custom'])
        self.assertEqual(result[10]['custom']['overall'], 'by_host')
        self.assertEqual(result[10]['instances'][101]['overall'], 'by_linked')

    def test_instance_ids_do_not_affect_type_sets(self):
        result = view(m_invisibleSet=[101], m_halftoneSet=[101], m_underlaySet=[101])
        self.assertTrue(result[10]['visible'])
        self.assertFalse(result[10]['halftone']); self.assertFalse(result[10]['underlay'])

    def test_ignored_display_entries(self):
        result = view(m_displaySettingsMap=[None, 7, {}, {'second': {}}, setting(10, 2)])
        self.assertEqual(result[10]['custom']['overall'], 'custom')

    def test_no_links(self):
        for f in (FakeF(), FakeF({'Other': [record(1)]})):
            self.assertEqual(L.view_links(f, {'m_pRvtLinkOverrides': pointer({
                'm_displaySettingsMap': [setting(10, 2)]})}), {})


if __name__ == '__main__':
    unittest.main()
