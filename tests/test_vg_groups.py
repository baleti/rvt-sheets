"""Characterise V/G group values using only synthetic decoded views."""
import os, sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.vg import groups


@pytest.fixture
def categories(monkeypatch):
    monkeypatch.setattr(groups, 'CAT_TYPES', {
        101: 'Model', 102: 'Annotation', 103: 'AnalyticalModel',
        104: 'Import', 105: 'Model',
    })
    return {201: {'parent': 101}, 202: {'parent': 102},
            203: {'parent': 103}, 204: {'parent': 104},
            205: {'parent': 201}, 999: {}, 998: None,
            101: {'parent': 102}}


@pytest.mark.parametrize('cid, expected', [
    (101, 'model'), (102, 'annotation'), (103, 'analytical'),
    (104, None), (999, None),
])
@pytest.mark.parametrize('with_cats', [False, True])
def test_cat_group_known_and_unknown(categories, cid, expected, with_cats):
    # Even an Import type does not currently map to the import group.
    if with_cats:
        assert groups.cat_group(cid, categories) == expected
    else:
        assert groups.cat_group(cid) == expected


@pytest.mark.parametrize('cid, expected', [
    (201, 'model'), (202, 'annotation'), (203, 'analytical'),
    (204, None), (205, None), (998, None), (997, None),
])
def test_cat_group_uses_only_immediate_parent(categories, cid, expected):
    assert groups.cat_group(cid, categories) == expected
    assert groups.cat_group(cid) is None
    assert groups.cat_group(cid, {}) is None


@pytest.mark.parametrize('view', [
    {}, {'draw_filters': None}, {'draw_filters': []},
    {'draw_filters': [{}]},
    {'draw_filters': [{'m_modelsExcluded': True}]},
    {'draw_filters': [{'m_categoryIds': None, 'm_modelsExcluded': True}]},
])
def test_excluded_set_without_category_wrapper(view):
    assert groups.excluded_set(view) == (set(), {})


@pytest.mark.parametrize('ids', [[], [101, 101, 102]])
@pytest.mark.parametrize('flags', [{}, {'m_modelsExcluded': None},
                                  {'m_modelsExcluded': 0}, {'m_modelsExcluded': 1}])
def test_excluded_set_returns_first_non_none_wrapper(ids, flags):
    wrapper = dict(flags, m_categoryIds=ids)
    view = {'draw_filters': [
        {'m_categoryIds': None}, wrapper,
        {'m_categoryIds': [999], 'm_modelsExcluded': True},
    ]}
    hidden, found = groups.excluded_set(view)
    assert hidden == set(ids)
    assert found is wrapper


@pytest.mark.parametrize('group, hidden, override_ids, excluded', [
    ('model', [101, 105, 201], [101, 201], 0),
    ('annotation', [102, 202], [102, 202], True),
    ('analytical', [103, 203], [103, 203], None),
    ('import', [], [], 1),
])
def test_value_category_partition(categories, group, hidden, override_ids, excluded):
    overrides = {cid: {'halftone': True, 'transparency': cid % 10}
                 for cid in [101, 102, 103, 104, 201, 202, 203, 204, 999]}
    view = {
        'draw_filters': [{
            'm_categoryIds': [999, 204, 203, 202, 201, 105, 104, 103, 102, 101, 101],
            'm_modelsExcluded': 0, 'm_annotationsExcluded': True,
            'm_analyticalModelsExcluded': None, 'm_importsExcluded': 1,
        }],
        'category_overrides': overrides,
    }
    assert groups.value(view, group, categories) == {
        'hidden': hidden, 'excluded': excluded,
        'overrides': {cid: overrides[cid] for cid in override_ids},
    }


@pytest.mark.parametrize('group', ['model', 'annotation', 'analytical', 'import'])
@pytest.mark.parametrize('view', [
    {}, {'category_overrides': None}, {'category_overrides': {}},
    {'draw_filters': None}, {'draw_filters': []},
    {'draw_filters': [{'m_categoryIds': []}]},
])
def test_value_empty_category_groups(categories, group, view):
    assert groups.value(view, group) == {
        'hidden': [], 'excluded': None, 'overrides': {},
    }


def test_value_hidden_without_overrides(categories):
    view = {'draw_filters': [{'m_categoryIds': [102, 101]}]}
    assert groups.value(view, 'model') == {
        'hidden': [101], 'excluded': None, 'overrides': {},
    }


def test_value_overrides_without_draw_filters(categories):
    view = {'category_overrides': {101: {'halftone': True}, 102: {}}}
    assert groups.value(view, 'model') == {
        'hidden': [], 'excluded': None, 'overrides': {101: {'halftone': True}},
    }


@pytest.mark.parametrize('group, key, payload', [
    ('filters', 'filters', [{'id': 7, 'visible': False}]),
    ('scale', 'scale', 100), ('detail_level', 'detail_level', 2),
    ('discipline', 'discipline', 3), ('phase_filter', 'phase_filter', 42),
    ('view_range', 'range', {'top': {'offset': 10}}),
    ('display_model', 'display_mode', 1),
])
def test_value_other_supported_groups(group, key, payload):
    assert groups.value({key: payload}, group) == payload
    assert groups.value({}, group) is None
    assert groups.value({key: None}, group) is None


def test_value_unknown_group():
    assert groups.value({'unknown': 123}, 'unknown') is None


@pytest.mark.parametrize('a, b, expected', [
    (None, None, True), (None, {}, False), ({}, {}, True),
    (1, 1, True), (1, 2, False), (1, True, False), (1, 1.0, False),
    ({'a': 1, 'b': 2}, {'b': 2, 'a': 1}, True),
    ({'a': [1, {'x': None, 'y': [2, 3]}]},
     {'a': [1, {'y': [2, 3], 'x': None}]}, True),
    ({'a': [1, 2]}, {'a': [2, 1]}, False),
    ({'a': {'b': 1}}, {'a': {'b': 2}}, False),
    ([1, 2], (1, 2), True), ({101: {'x': 1}}, {'101': {'x': 1}}, True),
    ({'x': 1 + 2j}, {'x': '(1+2j)'}, True),
])
def test_same_compares_json_serializations(a, b, expected):
    assert groups.same(a, b) is expected
