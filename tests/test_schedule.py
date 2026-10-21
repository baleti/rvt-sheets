"""Synthetic schedule tests; no Decoder, corpus, or Revit files required.

The source-only checkout omits reader/viewdraw. Import shims supply only the
reader constants and an explicit-newline wrapping boundary. Layout tests thus
exercise schedule's handling of wrapped text, not the absent font metrics.
Reader-dependent extraction, revision/name lookup and version detection are
intentionally out of scope.
"""
import importlib.util
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def modules(monkeypatch):
    root = Path(__file__).resolve().parents[1] / 'rvtsheets'
    package = types.ModuleType('_schedule_tests')
    package.__path__ = [str(root)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    reader = types.ModuleType('_schedule_tests.reader')
    reader.INVALID = -1
    # These are import-only shims: no reader-dependent helper is exercised.
    reader.ob = reader.path = None
    monkeypatch.setitem(sys.modules, reader.__name__, reader)
    # numpy is unused in schedule.py and need not be installed for these tests.
    viewdraw = types.ModuleType('_schedule_tests.viewdraw')
    viewdraw.wrap_text = lambda text, *args: text
    monkeypatch.setitem(sys.modules, viewdraw.__name__, viewdraw)
    loaded = []
    for name in ('units', 'schedule'):
        spec = importlib.util.spec_from_file_location(f'_schedule_tests.{name}', root / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        setattr(package, name, module)
        with monkeypatch.context() as imports:
            imports.setitem(sys.modules, 'numpy', types.ModuleType('numpy'))
            spec.loader.exec_module(module)
        loaded.append(module)
    for key in ('FIT', 'GL', 'EM', 'P', 'HDR', 'WRAP', 'OUTLINE', 'LW'):
        monkeypatch.delenv('RVT_SCHED_' + key, raising=False)
    return loaded[1], loaded[0]


@pytest.fixture
def sched(modules):
    schedule, _ = modules
    instance = object.__new__(schedule.Schedules)
    instance.f = object()  # Never used as a reader.
    return instance


@pytest.mark.parametrize('value,name,expected', [
    (None, '', ''), (True, '', 'Yes'), (False, '', 'No'),
    ('hello', '', 'hello'), ('', '', ''), (0, '', '0'),
    (1000, '', '1000'), (-1000, '', '-1000'), (-1, '', ''),
    (2001, 'Count', '2001'), (-1, 'Count', '-1'),
    (1.25, '', '1.25'), (2.0, None, '2'),
])
def test_scalar_formatting(sched, value, name, expected):
    assert sched.fmt(value, name) == expected


def test_element_id_format_dispatch(sched):
    calls = []
    sched.name_of = lambda eid, name: calls.append((eid, name)) or 'symbol'
    assert sched.fmt(1001, 'Type') == 'symbol'
    assert sched.fmt(-1001, 'Family') == 'symbol'
    assert calls == [(1001, 'Type'), (-1001, 'Family')]


@pytest.mark.parametrize('unit,accuracy,value,name,expected', [
    (2, 1, 1.0, 'Width', '305'), (0, .01, 10.0, 'Length', '3.05'),
    (4, 1/192, 1.5, 'Height', '1\' - 6"'),
    (3, .01, -1.25, 'Offset', '-1.25'),
    (2, 1, 100.0, 'Area', '9.29 m²'),
    (3, 1, 12.4, 'Area', '12 SF'),
    (2, 1, 100.0, 'Volume', '2.83 m³'),
    (4, 1, 12.5, 'Volume', '12.50 CF'),
])
def test_units_formatting(sched, modules, monkeypatch, unit, accuracy, value, name, expected):
    _, units = modules
    # Replace only project-option retrieval; use the real unit formatter.
    monkeypatch.setattr(units, 'length_format', lambda f: {'m_displayUnits': unit, 'm_accuracy': accuracy})
    assert sched.fmt(value, name) == expected


@pytest.mark.parametrize('name', ['Length', 'Offset', 'Width', 'Height', 'Elevation', 'Thickness', 'Depth', 'Perimeter', 'Diameter', 'Radius', 'Size'])
def test_all_length_captions(sched, modules, monkeypatch, name):
    monkeypatch.setattr(modules[1], 'length_format', lambda f: {'m_displayUnits': 2, 'm_accuracy': 1})
    assert sched.fmt(1.0, 'Nominal ' + name) == '305'


@pytest.mark.parametrize('value,raw,has,heading,expected', [
    (True, {}, False, 'Enabled?', 'Yes'),
    (False, {}, False, 'Enabled?', 'No'),
    (None, {7: None}, False, 'Enabled?  ', 'No'),
    (None, {}, True, 'Enabled?', 'No'),
    (None, {}, False, 'Enabled?', ''),
    (None, {7: None}, True, 'Enabled', ''),
])
def test_yes_no_cells(sched, value, raw, has, heading, expected):
    sched.value = lambda *args: value
    sched._raw = lambda eid: raw
    sched._raw_has = lambda eid, pid: has
    assert sched.cell_text(1, {'heading': heading, 'param': 7, 'pname': 'Enabled'}, {}) == expected


def row_input(sched, records):
    sched.sc_vis_info = lambda: {eid: {'cat': 42, 'owner': -1, 'type': False, **info} for eid, info, values in records}
    values = {eid: v for eid, info, v in records}
    sched.params = lambda: {}
    sched.value = lambda eid, field, named: values[eid][field['index']]
    sched.cell_text = lambda eid, field, named: str(values[eid][field['index']])
    fields = [{'index': 0}, {'index': 1}]
    return {'category': 42, 'instance': True, 'fields': [fields[1]], 'all_fields': fields, 'field_ids': [91, 37], 'sort': []}


def test_sort_hidden_field_ids_numeric_and_stable_ties(sched):
    d = row_input(sched, [(8, {}, [2, 'eight']), (3, {}, [10, 'three']), (2, {}, [2, 'two'])])
    d['sort'] = [(91, 0)]
    assert sched.rows(d) == [['two'], ['eight'], ['three']]
    d['sort'] = [(91, 1)]
    assert sched.rows(d) == [['three'], ['two'], ['eight']]
    d['sort'] = [(0, 0)]  # Legacy field-index fallback.
    assert sched.rows(d) == [['two'], ['eight'], ['three']]


def test_multiple_sort_keys_and_invalid_fields(sched):
    d = row_input(sched, [(4, {}, ['b', 'a']), (3, {}, ['a', 'a']), (2, {}, ['a', 'z'])])
    d['sort'] = [(91, 0), (37, 1), (999, 0)]
    assert sched.rows(d) == [['z'], ['a'], ['a']]
    d['sort'] = [(999, 0)]
    assert sched.rows(d) == [['z'], ['a'], ['a']]
    assert sched.rows({**d, 'category': 99}) == []


def test_mixed_sort_values_and_no_implicit_grouping_or_totals(sched):
    d = row_input(sched, [(5, {}, ['2', 'text']), (4, {}, [10, 'number']), (3, {}, [None, 'empty']), (2, {}, [True, 'bool']), (1, {}, [10, 'number'])])
    d['sort'] = [(91, 0)]
    assert sched.rows(d) == [['number'], ['number'], ['empty'], ['text'], ['bool']]


def test_category_owner_and_instance_filters(sched, modules):
    d = row_input(sched, [(1, {}, [0, 'instance']), (2, {'type': True}, [0, 'type']), (3, {'owner': 50}, [0, 'owned']), (4, {'cat': 99}, [0, 'other'])])
    assert sched.rows(d) == [['instance']]
    assert sched.rows({**d, 'instance': False}) == [['type']]
    annotation = modules[0].ANNOTATION_SYMBOLS
    d = row_input(sched, [(1, {'cat': annotation, 'owner': 50}, [0, 'annotation'])])
    assert sched.rows({**d, 'category': annotation}) == [['annotation']]


@pytest.fixture
def layout(sched):
    font = (.01, 'Arial', False)
    d = dict(fields=[{'heading': 'A', 'width': 1., 'groups': []}, {'heading': 'B', 'width': 1., 'groups': []}],
             title='Title', title_h=.1, body_h=.1, show_title=False, show_headers=False,
             fixed=False, height=None, tb_inst=None, grid_lines=1, outline=1,
             grid_gs=10, outline_gs=20, medium_gs=30, header_set={},
             fonts={key: font for key in ('m_titleTextTypeId', 'm_headerTextTypeId', 'm_bodyTextTypeId')})
    rows = [['one', 'two']]
    sched.definition = lambda sid: d
    sched.rows = lambda *args: rows
    sched.old_em = lambda d: False
    return sched, d, rows


def texts(prims):
    return [p for p in prims if p['t'] == 'text']


def lines(prims):
    return [p for p in prims if p['t'] == 'line']


def test_basic_layout_and_outline(layout):
    s, d, rows = layout
    p = s.prims(123, (2, 3))
    assert [t['text'] for t in texts(p)] == ['one', 'two']
    assert texts(p)[0]['origin'] == pytest.approx([2.004, 2.95, 0])
    assert texts(p)[0]['size'] == pytest.approx(.01)
    assert all(x['elem'] == 123 for x in p)
    assert [x['gs'] for x in lines(p)] == [10, 20, 10, 20]
    assert [x['w_min'] for x in lines(p)] == [0, .457, 0, .457]


def test_wrapped_body_grows_by_extra_line_pitch(layout):
    s, d, rows = layout
    rows[:] = [['first\nsecond\nthird', 'peer'], ['next', 'row']]
    p = s.prims(1, (0, 0))
    height = .1 + 2 * (.01 / .72) * 1.22
    assert lines(p)[0]['pts'][0][1] == pytest.approx(-height)
    assert texts(p)[2]['origin'][1] == pytest.approx(-height - .05)
    assert texts(p)[0]['valign'] == 0
    assert texts(p)[1]['valign'] == 0
    assert texts(p)[0]['text'] == 'first\nsecond\nthird'


def test_group_headers_merge_only_caption_row(layout):
    s, d, rows = layout
    d['show_headers'] = True
    for f in d['fields']: f['groups'] = [7]
    d['header_set'] = {7: 'Group'}
    p = s.prims(1, (0, 0))
    assert [t['text'] for t in texts(p)] == ['Group', 'A', 'B', 'one', 'two']
    assert texts(p)[0]['origin'] == pytest.approx([1, -.05, 0])
    vertical = [l for l in lines(p) if l['pts'][0][0] == l['pts'][1][0]]
    assert vertical[1]['pts'][0] == [1, -.1, 0]
    assert vertical[0]['pts'][0] == [0, 0, 0]
    assert texts(p)[3]['origin'][1] == pytest.approx(-.25)


def test_note_row_merges_width_and_clips_lines(layout):
    s, d, rows = layout
    d.update(show_title=True, title_size=.02, header_rows=[{'text': 'note\nextra', 'size': .01, 'font': 'Arial', 'height': .02}])
    p = s.prims(1, (0, 0))
    assert [t['text'] for t in texts(p)][:2] == ['Title', 'note...']
    assert texts(p)[0]['size'] == pytest.approx(.02)
    assert texts(p)[1]['origin'][0] == .004
    assert texts(p)[2]['origin'][1] == pytest.approx(-.17)
    inner = [l for l in lines(p) if l['pts'][0][0] == l['pts'][1][0] == 1]
    assert len(inner) == 1
    assert inner[0]['pts'][0][1] == pytest.approx(-.12)


def test_header_wrap_growth_and_toggle(layout, monkeypatch):
    s, d, rows = layout
    d['show_headers'] = True
    d['fields'][0].update(heading='Long heading', width=.04)
    p = s.prims(1, (0, 0))
    assert [t['text'] for t in texts(p)][:3] == ['Long', 'heading', 'B']
    assert texts(p)[3]['origin'][1] == pytest.approx(-.15 - .01/.72*1.26)
    monkeypatch.setenv('RVT_SCHED_WRAP', '0')
    p = s.prims(1, (0, 0))
    assert texts(p)[0]['text'] == 'Long heading'
    assert texts(p)[2]['origin'][1] == pytest.approx(-.15)


def test_fixed_height_adds_blank_rows_without_text(layout):
    s, d, rows = layout
    d.update(fixed=True, height=.4)
    p = s.prims(1, (0, 0))
    assert len(texts(p)) == 2
    assert len(lines(p)) == 7
    assert lines(p)[3]['pts'][0][1] == pytest.approx(-.4)
    d['height'] = .01
    assert len(lines(s.prims(1, (0, 0)))) == 4


def test_gridless_hidden_header_spacer(layout):
    s, d, rows = layout
    d.update(grid_lines=0, show_title=True)
    p = s.prims(1, (0, 0))
    assert lines(p) == []
    assert texts(p)[1]['origin'][1] == pytest.approx(-.25)


def test_initial_spacer_and_larger_header_font(layout):
    s, d, rows = layout
    d.update(show_headers=True, initial_spacer=True)
    d['fonts']['m_headerTextTypeId'] = (.02, 'Arial', True)
    p = s.prims(1, (0, 0))
    assert texts(p)[0]['origin'][1] == pytest.approx(-.1)
    assert texts(p)[2]['origin'][1] == pytest.approx(-.35)
    assert texts(p)[0]['bold'] is True


def test_missing_definition_and_empty_fields(layout):
    s, d, rows = layout
    d['fields'] = []
    assert s.prims(1, (0, 0)) == []
    s.definition = lambda sid: None
    assert s.prims(1, (0, 0)) == []


@pytest.mark.parametrize('env,definition,expected', [
    ({}, {}, 1/.72), ({}, {'grid_lines': 0}, 1/.72),
    ({'FIT': '0'}, {}, .8), ({'FIT': '0'}, {'grid_lines': 0}, 1.2),
    ({'GL': '0'}, {'grid_lines': 0}, 1.2),
])
def test_em_environment_branches(sched, monkeypatch, env, definition, expected):
    for key, value in env.items(): monkeypatch.setenv('RVT_SCHED_' + key, value)
    assert sched.em_k(definition) == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason='bug: stored integer Yes/No values render as 0/1 instead of No/Yes')
@pytest.mark.parametrize('value,expected', [(0, 'No'), (1, 'Yes')])
def test_integer_yes_no_cells(sched, value, expected):
    sched.value = lambda *args: value
    sched._raw = lambda eid: {7: value}
    sched._raw_has = lambda eid, pid: True
    assert sched.cell_text(1, {'heading': 'Enabled?', 'param': 7, 'pname': 'Enabled'}, {}) == expected


def test_primary_sort_precedes_secondary_sort(sched):
    d = row_input(sched, [(1, {}, ['b', 'z']), (2, {}, ['a', 'a']), (3, {}, ['a', 'y'])])
    d['sort'] = [(91, 0), (37, 1)]
    assert sched.rows(d) == [['y'], ['a'], ['z']]


def test_empty_rows(sched):
    d = row_input(sched, [])
    d['sort'] = [(91, 1)]
    assert sched.rows(d) == []


def test_separate_header_groups_and_ungrouped_heading(layout):
    s, d, rows = layout
    d['show_headers'] = True
    d['fields'] = [
        {'heading': 'A', 'width': 1., 'groups': [7]},
        {'heading': 'Plain', 'width': 1., 'groups': []},
        {'heading': 'C', 'width': 1., 'groups': [7]},
    ]
    d['header_set'] = {7: 'Group'}
    rows[:] = []
    p = s.prims(1, (0, 0))
    assert [t['text'] for t in texts(p)] == ['Group', 'A', 'Plain', 'Group', 'C']
    assert [t['origin'][0] for t in texts(p) if t['text'] == 'Group'] == [.5, 2.5]
    assert texts(p)[2]['origin'][1] == pytest.approx(-.15)
    vertical = [l for l in lines(p) if l['pts'][0][0] == l['pts'][1][0]]
    assert all(l['pts'][0][1] == 0 for l in vertical)


def test_note_without_explicit_height_uses_one_line_pitch(layout):
    s, d, rows = layout
    d['header_rows'] = [{'text': 'note', 'size': .01, 'font': 'Arial', 'height': None}]
    p = s.prims(1, (0, 0))
    assert texts(p)[0]['text'] == 'note'
    assert texts(p)[1]['origin'][1] == pytest.approx(-.01/.72*1.22 - .05)


def test_gridless_minimum_body_pitch(layout):
    s, d, rows = layout
    d.update(grid_lines=0, body_h=.001)
    rows[:] = [['a', 'b'], ['c', 'd']]
    p = s.prims(1, (0, 0))
    assert texts(p)[0]['origin'][1] - texts(p)[2]['origin'][1] == pytest.approx(.01*1.917)
    assert lines(p) == []
