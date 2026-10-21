"""viewsvg.body drops line segments / polylines that repeat an earlier one (same style, layer), restarting at every fill or image"""
import xml.etree.ElementTree as ET
import pytest
from rvtsheets import viewsvg

ST = {'w': 0.127, 'rgb': [0, 0, 0], 'dash': None}


def render(prims):
    out = viewsvg.body(prims, 100, lambda u, v: (u, v))
    return ET.fromstring('<g xmlns="http://www.w3.org/2000/svg">' + ''.join(out) + '</g>')


def paths(prims):
    return [n.get('d') for n in render(prims)]


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv('RVT_DEDUPE', '1')


def line(pts, layer='projection', style=None, elem=1):
    return {'t': 'line', 'pts': pts, 'style': style or ST, 'layer': layer, 'elem': elem}


def segs(ss, layer='projection', style=None, elem=1):
    return {'t': 'segs', 'segs': ss, 'style': style or ST, 'layer': layer, 'elem': elem}


def test_identical_lines_drawn_once():
    assert len(paths([line([[0, 0], [1, 0]]), line([[0, 0], [1, 0]], elem=2)])) == 1


def test_reversed_line_is_a_duplicate():
    assert len(paths([line([[0, 0], [1, 0]]), line([[1, 0], [0, 0]])])) == 1


def test_different_style_or_layer_kept():
    assert len(paths([line([[0, 0], [1, 0]]), line([[0, 0], [1, 0]], style=dict(ST, w=0.3))])) == 2
    assert len(paths([line([[0, 0], [1, 0]]), line([[0, 0], [1, 0]], layer='symbolic')])) == 2
    assert len(paths([line([[0, 0], [1, 0]]), line([[0, 0], [1, 0]], style=dict(ST, dash=[2, 1]))])) == 2


def test_segments_filtered_inside_a_prim_and_across_prims():
    d = paths([segs([[[0, 0], [1, 0]], [[0, 1], [1, 1]], [[1, 0], [0, 0]]]), segs([[[0, 1], [1, 1]], [[0, 2], [1, 2]]])])
    assert len(d) == 2
    assert d[0].count('M') == 2 and d[1].count('M') == 1


def test_prim_with_only_duplicates_disappears():
    assert len(paths([segs([[[0, 0], [1, 0]]]), segs([[[0, 0], [1, 0]]])])) == 1


def test_fill_restarts_the_seen_set():
    fill = {'t': 'fill', 'loops': [[[0, 0], [1, 0], [1, 1], [0, 0]]], 'color': [255, 255, 255], 'layer': 'projection', 'elem': 3}
    n = render([line([[0, 0], [1, 0]]), fill, line([[0, 0], [1, 0]])])
    assert sum(1 for x in n if x.get('stroke') == '#000000') == 2


def test_rounding_tolerance_and_off_switch(monkeypatch):
    assert len(paths([line([[0, 0], [1, 0]]), line([[0.00001, 0], [1.00002, 0]])])) == 1
    monkeypatch.setenv('RVT_DEDUPE', '0')
    assert len(paths([line([[0, 0], [1, 0]]), line([[0, 0], [1, 0]])])) == 2


def test_different_segments_untouched():
    assert len(paths([line([[0, 0], [1, 0]]), line([[0, 0], [2, 0]])])) == 2
