"""Characterize template helpers using synthetic view dictionaries only."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.vg import template as T


GROUP_ORDER = [
    'model', 'annotation', 'import', 'analytical', 'filters', 'links',
    'design_options', 'scale', 'detail_level', 'parts_visibility', 'discipline',
    'phase_filter', 'view_range', 'orientation', 'display_model', 'model_display',
    'shadows', 'lighting', 'background', 'exposure', 'far_clip', 'depth_clip',
    'hidden_lines', 'sketchy', 'underlay_orientation', 'color_scheme', 'cropping',
]


@pytest.mark.parametrize('template_id', [None, T.INVALID, -1],
                         ids=['none', 'invalid', 'minus_one'])
def test_template_of_sentinel(template_id):
    # Even a template stored at a sentinel key is ignored.
    views = {template_id: {'template': True}}
    assert T.template_of(views, {'view_template': template_id}) is None


def test_template_of_absent_field():
    assert T.template_of({1: {'template': True}}, {}) is None


@pytest.mark.parametrize('stored_key', [7, '7'])
def test_template_of_integer_id_with_integer_or_string_key(stored_key):
    tpl = {'template': True}
    assert T.template_of({stored_key: tpl}, {'view_template': 7}) is tpl


@pytest.mark.parametrize('candidate', [{'template': False}, {'name': 'View'}, {}])
def test_template_of_non_template(candidate):
    assert T.template_of({7: candidate}, {'view_template': 7}) is None


def test_template_of_missing_key():
    assert T.template_of({}, {'view_template': 7}) is None


def test_template_of_prefers_integer_key():
    integer_tpl = {'template': True}
    string_tpl = {'template': True}
    assert T.template_of({7: integer_tpl, '7': string_tpl},
                         {'view_template': 7}) is integer_tpl


def test_template_of_truthy_non_template_blocks_string_fallback():
    views = {7: {'template': False}, '7': {'template': True}}
    assert T.template_of(views, {'view_template': 7}) is None


def test_template_of_empty_integer_value_uses_string_fallback():
    tpl = {'template': True}
    assert T.template_of({7: {}, '7': tpl}, {'view_template': 7}) is tpl


@pytest.mark.parametrize('tpl, expected', [
    ({}, set()),
    ({'non_propagated_template_params': None}, set()),
    ({'non_propagated_template_params': []}, set()),
    ({'non_propagated_template_params': [-1006961, -1006961, -1006962]},
     {-1006961, -1006962}),
])
def test_excluded_ids(tpl, expected):
    result = T.excluded_ids(tpl)
    assert isinstance(result, set)
    assert result == expected


@pytest.mark.parametrize('group', GROUP_ORDER)
@pytest.mark.parametrize('excluded', [False, True])
def test_controls_each_group(group, excluded):
    tpl = {'template': True, 'non_propagated_template_params':
           list(T.GROUP_PARAMS[group]) if excluded else []}
    assert T.controls(tpl, group) is (not excluded)


@pytest.mark.parametrize('group', GROUP_ORDER)
def test_controls_none_template(group):
    assert T.controls(None, group) is False


@pytest.mark.parametrize('group, excluded_id', [
    ('scale', -1005152), ('scale', -1005151), ('scale', -1005150),
    ('color_scheme', -1005148), ('color_scheme', -1005183),
])
def test_controls_one_excluded_id_disables_multi_id_group(group, excluded_id):
    tpl = {'template': True, 'non_propagated_template_params': [excluded_id]}
    assert T.controls(tpl, group) is False


def test_controls_unknown_group_raises_key_error():
    with pytest.raises(KeyError) as exc:
        T.controls({'template': True}, 'unknown')
    assert exc.value.args == ('unknown',)


def test_controls_none_template_short_circuits_unknown_group():
    assert T.controls(None, 'unknown') is False


@pytest.mark.parametrize('excluded', [None, []])
def test_controlled_groups_all_in_order(excluded):
    tpl = {'template': True, 'non_propagated_template_params': excluded}
    assert T.controlled_groups(tpl) == GROUP_ORDER


def test_controlled_groups_always_excluded():
    tpl = {'template': True,
           'non_propagated_template_params': list(T.ALWAYS_EXCLUDED)}
    assert T.controlled_groups(tpl) == [
        group for group in GROUP_ORDER
        if group not in ('underlay_orientation', 'color_scheme')
    ]


def test_controlled_groups_none_template():
    assert T.controlled_groups(None) == []


def test_group_keys_unique_and_ordered():
    keys = list(T.GROUP_PARAMS)
    assert len(keys) == len(set(keys))
    assert keys == GROUP_ORDER


def test_parameter_ids_are_negative_integers():
    ids = [p for params in T.GROUP_PARAMS.values() for p in params]
    ids.extend(T.SCALE_IDS)
    ids.extend(T.ALWAYS_EXCLUDED)
    assert all(type(p) is int and p < 0 for p in ids)


def test_scale_ids_belong_to_scale_group():
    assert T.SCALE_IDS == (-1005152, -1005151, -1005150)
    assert T.GROUP_PARAMS['scale'] == T.SCALE_IDS


def test_always_excluded_membership_in_groups():
    assert T.ALWAYS_EXCLUDED == (-1133900, -1005183, -1005177, -1005148)
    group_ids = {p for params in T.GROUP_PARAMS.values() for p in params}
    assert set(T.ALWAYS_EXCLUDED) & group_ids == {-1005183, -1005177, -1005148}
    assert set(T.ALWAYS_EXCLUDED) - group_ids == {-1133900}
